"""Bilingual ASS with separate anchors; no full-width background bars."""
from pathlib import Path
from core import caption_anchors


def ass_time(seconds):
    n = round(seconds * 100)
    return f"{n // 360000}:{n // 6000 % 60:02d}:{n // 100 % 60:02d}.{n % 100:02d}"


def srt_time(seconds):
    n = round(seconds * 1000)
    return f"{n // 3600000:02d}:{n // 60000 % 60:02d}:{n // 1000 % 60:02d},{n % 1000:03d}"


def escape_ass(text):
    # Neutralize ASS override injection. Explicit text newlines remain intentional.
    return text.replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\n", r"\N")


def create(project, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    p = project["profile"]
    width, height = p["width"], p["height"]
    scale = height / 1080
    font = p.get("font", "Noto Sans CJK SC")
    if any(c in font for c in ",\n\r"):
        raise ValueError("Font name cannot contain ASS field separators")
    top_size = round(p.get("top_font_size", 40) * scale)
    bottom_size = round(p.get("bottom_font_size", 34) * scale)
    # Top anchor grows upward, bottom anchor grows downward: multi-line pairs cannot collide.
    caption_anchors(p)  # Validate defaults even for an empty caption track.
    margin = round(width * .05)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Top,{font},{top_size},&H00FFFFFF,&H00FFFFFF,&H00202020,&H00000000,0,0,0,0,100,100,0,0,1,{2 * scale:.2f},{scale:.2f},2,{margin},{margin},0,1
Style: Bottom,{font},{bottom_size},&H00FFFFFF,&H00FFFFFF,&H00202020,&H00000000,0,0,0,0,100,100,0,0,1,{2 * scale:.2f},{scale:.2f},8,{margin},{margin},0,1
[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    events, srt = [], []
    for i, cue in enumerate(project.get("captions", []), 1):
        top_y, bottom_y = caption_anchors(p, cue)
        for field, style, y in (("top", "Top", top_y), ("bottom", "Bottom", bottom_y)):
            if not cue.get(field):
                continue
            tag = r"{\pos(" + f"{width // 2},{y}" + r")\fad(50,70)}"
            events.append(f"Dialogue: 0,{ass_time(cue['start'])},{ass_time(cue['end'])},{style},,0,0,0,,{tag}{escape_ass(cue[field])}")
        content = "\n".join(cue[field] for field in ("top", "bottom") if cue.get(field))
        srt.append(f"{i}\n{srt_time(cue['start'])} --> {srt_time(cue['end'])}\n{content}\n")
    ass_path, srt_path = directory / "captions.ass", directory / "captions.srt"
    ass_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    srt_path.write_text("\n".join(srt), encoding="utf-8")
    return ass_path, srt_path
