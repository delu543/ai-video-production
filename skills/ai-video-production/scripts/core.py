"""Portable project contract and deterministic preflight. Standard library only."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

VERSION = "0.1.2"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".writing")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def binary(name):
    value = os.environ.get(name.upper() + "_BIN") or shutil.which(name)
    if not value or not Path(value).is_file():
        raise ValueError(f"Missing {name}: add to PATH or set {name.upper()}_BIN")
    return value


def run(args):
    result = subprocess.run([str(a) for a in args], capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f"Command failed ({Path(str(args[0])).name}): {result.stderr[-4000:]}")
    return result


def probe(path, count=False):
    args = [binary("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json"]
    if count:
        args.append("-count_frames")
    return json.loads(run(args + [path]).stdout)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def media_path(root, value):
    """Manifest paths are relative and cannot escape the project, even via symlinks."""
    path = Path(value)
    root = Path(root).resolve()
    resolved = (root / path).resolve()
    if path.is_absolute() or not resolved.is_relative_to(root):
        raise ValueError(f"Media path must stay inside project: {value}")
    return resolved


def number(value, label, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label}: finite number required")
    if value < minimum:
        raise ValueError(f"{label}: must be >= {minimum}")
    return value


def timing(project):
    """Durations include transition overlap. Global boundaries avoid rounding drift."""
    fps = project["profile"]["fps"]
    start = 0.0
    rows = []
    for index, shot in enumerate(project["shots"]):
        duration = number(shot["duration"], "shot.duration", 1 / fps)
        transition = shot.get("transition", {"type": "cut", "duration": 0})
        overlap = number(transition.get("duration", 0), "transition.duration")
        if index == 0 and overlap:
            raise ValueError("First shot cannot have incoming overlap")
        if index:
            start -= overlap
        end = start + duration
        row = dict(shot, start=start, end=end, first=round(start * fps), last=round(end * fps))
        row["frames"] = row["last"] - row["first"]
        row["incoming"] = rows[-1]["last"] - row["first"] if rows else 0
        if row["incoming"] < 0 or row["incoming"] >= row["frames"]:
            raise ValueError("Transition exceeds shot duration")
        if rows and rows[-1]["incoming"] + row["incoming"] >= rows[-1]["frames"]:
            raise ValueError("Adjacent transitions consume the entire intervening shot")
        rows.append(row)
        start = end
    return rows, rows[-1]["last"] if rows else 0


def validate(project, root, stage="design", allow_test=False):
    errors, warnings = [], []
    try:
        if project.get("schema_version") != 1:
            raise ValueError("schema_version must be 1")
        profile = project["profile"]
        for field in ("width", "height", "fps"):
            number(profile[field], field, 1)
            if not isinstance(profile[field], int):
                raise ValueError(f"{field}: integer required")
        if profile["width"] % 2 or profile["height"] % 2:
            errors.append("Width/height must be even for yuv420p")
        rows, frames = timing(project)
        if not rows:
            errors.append("No shots")
        total = frames / profile["fps"]
        assets = project.get("assets", {})
        beats = {b["id"]: b for b in project.get("beats", [])}
        if len(beats) != len(project.get("beats", [])):
            errors.append("Duplicate beat IDs")
        facts = {f["id"]: f for f in project.get("facts", [])}
        for fact in facts.values():
            if fact.get("status") != "checked" or not fact.get("sources") or not fact.get("claim"):
                errors.append(f"Fact {fact['id']}: unchecked or missing evidence")
        for beat in beats.values():
            if not beat.get("narration") and not beat.get("original_quote") and not beat.get("silence_reason"):
                errors.append(f"Beat {beat['id']}: no narration, original quote or intentional silence")
            for fact in beat.get("fact_ids", []):
                if fact not in facts:
                    errors.append(f"Beat {beat['id']}: unknown fact {fact}")
        if not beats:
            errors.append("No narrative beats")
        uses, covered, used = {}, set(), set()
        for i, shot in enumerate(rows):
            sid = shot.get("id", str(i))
            asset_id = shot["asset_id"]
            if asset_id not in assets:
                errors.append(f"Shot {sid}: missing asset {asset_id}")
                continue
            asset = assets[asset_id]
            if asset.get("kind") not in ("video", "still"):
                errors.append(f"Shot {sid}: needs video/still")
            used.add(asset_id)
            group = asset.get("source_group", asset_id)
            uses[group] = uses.get(group, 0) + 1
            if shot.get("beat_id") not in beats or not shot.get("purpose"):
                errors.append(f"Shot {sid}: narrative binding/purpose missing")
            covered.add(shot.get("beat_id"))
            if shot.get("framing", "cover") not in ("cover", "contain"):
                errors.append(f"Shot {sid}: unknown framing")
            if shot.get("crop"):
                crop = shot["crop"]
                if len(crop) != 4 or any(not isinstance(n, int) or n < 0 for n in crop) or min(crop[:2]) <= 0:
                    errors.append(f"Shot {sid}: crop is [width,height,x,y] in source pixels")
            zoom = number(shot.get("zoom", 0), "zoom")
            if zoom > 0.08 or (zoom and asset.get("kind") != "still"):
                errors.append(f"Shot {sid}: zoom supports stills only, range 0..0.08")
            if zoom and shot.get("framing") == "contain":
                errors.append(f"Shot {sid}: contained still motion needs a dedicated compositor")
            tr = shot.get("transition", {})
            if tr.get("type", "cut") not in ("cut", "dissolve"):
                errors.append(f"Shot {sid}: unsupported transition")
            overlap = tr.get("duration", 0)
            if tr.get("type", "cut") == "cut" and overlap != 0:
                errors.append(f"Shot {sid}: cut must have zero overlap")
            if tr.get("type") == "dissolve" and shot["incoming"] < 2:
                errors.append(f"Shot {sid}: dissolve must span at least two frames")
            if i and not tr.get("relation"):
                errors.append(f"Shot {sid}: transition relation missing")
            if i and tr.get("type", "cut") == "cut" and not tr.get("cut_reason"):
                errors.append(f"Shot {sid}: direct cut needs a reason")
            source_in = number(shot.get("source_in", 0), "source_in")
            speed = number(shot.get("speed", 1), "speed", 0.1)
            if speed != 1 and not shot.get("speed_reason"):
                errors.append(f"Shot {sid}: speed change needs a reason")
            if asset.get("kind") == "video" and source_in + shot["duration"] * speed > asset.get("duration", 0) + 1 / profile["fps"]:
                errors.append(f"Shot {sid}: source interval exceeds available footage")
        for beat_id in beats:
            if beat_id not in covered:
                errors.append(f"Beat {beat_id}: no bound picture")
        limit = project.get("quality", {}).get("max_asset_uses", 2)
        for group, count in uses.items():
            if count > limit and not project.get("reuse_exceptions", {}).get(group):
                errors.append(f"Source {group}: {count} uses exceeds limit {limit}")
        previous_end = 0
        for cue in project.get("captions", []):
            start = number(cue["start"], "caption.start")
            end = number(cue["end"], "caption.end")
            if start < previous_end or end <= start or end > total + 1 / profile["fps"]:
                errors.append("Caption overlaps another caption or exceeds timeline")
            previous_end = end
            for field in ("top", "bottom"):
                text = cue.get(field, "")
                if not text or len(text.splitlines()) > 2:
                    errors.append(f"Caption {field}: required, at most two explicit lines")
                if len(text) > (90 if profile.get(field + "_language") == "en" else 50):
                    warnings.append(f"Long {field} caption: preview actual glyph width")
        for cue in project.get("audio_cues", []):
            aid = cue["asset_id"]
            used.add(aid)
            if aid not in assets or assets[aid].get("kind") != "audio":
                errors.append(f"Audio {cue.get('id')}: unknown/non-audio asset")
                continue
            start = number(cue["start"], "audio.start")
            length = number(cue["duration"], "audio.duration", 0.001)
            source_in = number(cue.get("source_in", 0), "audio.source_in")
            if start + length > total + 1 / profile["fps"] or source_in + length > assets[aid].get("duration", 0) + .01:
                errors.append(f"Audio {cue.get('id')}: interval exceeds timeline/source")
            if cue.get("role") not in ("narration", "original", "music", "ambience"):
                errors.append("Unknown audio role")
            if cue.get("role") == "music" and not cue.get("selection_reason"):
                errors.append("Music cue needs a narrative selection reason")
            if number(cue.get("fade_in", 0), "fade_in") + number(cue.get("fade_out", 0), "fade_out") > length:
                errors.append("Audio fades exceed duration")
            last = -1
            for t, gain in cue.get("envelope", []):
                number(t, "envelope.time")
                number(gain, "envelope.gain_db", -120)
                if t <= last or t > length:
                    errors.append("Envelope times must increase within cue")
                last = t
        if any(c.get("role") == "music" for c in project.get("audio_cues", [])) and not project.get("music_plan", {}).get("palette"):
            errors.append("Music needs an overall palette and emotional plan")
        for aid in used:
            if aid not in assets:
                continue
            asset = assets[aid]
            path = media_path(root, asset["path"])
            if not asset.get("source_url") or not asset.get("creator"):
                errors.append(f"Asset {aid}: source/creator missing")
            origin = asset.get("origin")
            if origin == "synthetic_test" and not allow_test:
                errors.append(f"Asset {aid}: synthetic fixture forbidden in production")
            if origin == "generated" and asset.get("kind") != "audio" and not project.get("quality", {}).get("allow_generated_visuals", False):
                errors.append(f"Asset {aid}: generated visuals forbidden")
            if origin not in ("real", "archival", "self_recorded", "authored_graphic", "generated", "synthetic_test"):
                errors.append(f"Asset {aid}: origin missing/invalid")
            if not asset.get("rights_status"):
                errors.append(f"Asset {aid}: rights status missing")
            if stage == "publish" and (asset.get("rights_status") != "cleared" or not asset.get("rights_basis")):
                errors.append(f"Asset {aid}: reuse rights not cleared")
            if asset.get("kind") in ("video", "still"):
                quality = asset.get("quality", {})
                if quality.get("review") != "passed":
                    errors.append(f"Asset {aid}: actual quality review missing")
                ew, eh = quality.get("effective_width", 0), quality.get("effective_height", 0)
                if min(ew, eh) <= 0:
                    errors.append(f"Asset {aid}: effective resolution missing")
                related = [s for s in rows if s["asset_id"] == aid]
                # Compare to actual foreground display, not to full output for contained archives.
                for shot in related:
                    ratio = min(profile["width"] / ew, profile["height"] / eh) if shot.get("framing") == "contain" else max(profile["width"] / ew, profile["height"] / eh)
                    ratio *= 1 + shot.get("zoom", 0)
                    if ratio > 1.05 and not quality.get("exception_reason"):
                        errors.append(f"Asset {aid}: effective pixels require {ratio:.2f}x upscale; replace or justify archive exception")
            if stage in ("render", "publish"):
                if not path.is_file():
                    errors.append(f"Missing local media: {asset['path']}")
                    continue
                metadata = probe(path)
                streams = metadata["streams"]
                video = next((s for s in streams if s.get("codec_type") == "video"), None)
                if video and video.get("color_transfer") in ("smpte2084", "arib-std-b67"):
                    errors.append(f"Asset {aid}: HDR needs a verified SDR conversion before this renderer")
                if asset.get("kind") in ("video", "still"):
                    if video is None:
                        errors.append(f"Asset {aid}: not decodable picture")
                    else:
                        q = asset.get("quality", {})
                        if q.get("effective_width", 0) > video["width"] or q.get("effective_height", 0) > video["height"]:
                            errors.append(f"Asset {aid}: declared quality exceeds decoded dimensions")
                        for shot in [s for s in rows if s["asset_id"] == aid and s.get("crop")]:
                            w, h, x, y = shot["crop"]
                            if w + x > video["width"] or h + y > video["height"]:
                                errors.append(f"Asset {aid}: crop exceeds source")
                            if q.get("effective_width", 0) > w or q.get("effective_height", 0) > h:
                                errors.append(f"Asset {aid}: quality ignores crop loss")
                elif not any(s.get("codec_type") == "audio" for s in streams):
                    errors.append(f"Asset {aid}: no audio stream")
                duration = float(metadata.get("format", {}).get("duration", asset.get("duration", 0)))
                if asset.get("kind") != "still" and asset.get("duration", 0) > duration + .1:
                    errors.append(f"Asset {aid}: declared duration exceeds probed source")
        budget = project.get("budget", {})
        number(budget.get("cap", 0), "budget.cap")
        if budget.get("cap", 0) and not budget.get("authorization"):
            errors.append("Positive budget requires recorded authorization scope")
        if stage == "publish":
            for gate in ("editorial", "picture", "voice", "music", "captions", "continuity", "listening"):
                if project.get("reviews", {}).get(gate) != "passed":
                    errors.append(f"Publication review pending: {gate}")
        return {"ok": not errors, "errors": errors, "warnings": sorted(set(warnings)), "frames": frames, "duration": total, "asset_uses": uses}
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        return {"ok": False, "errors": errors + [f"Invalid project: {exc}"], "warnings": warnings}
