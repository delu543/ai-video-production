"""Explicit cue arrangement, automation and measured two-pass loudness."""
import json
from pathlib import Path
from core import binary, media_path, run, timing, write_json


def measurement(path, target=-16, peak=-2):
    result = run([binary("ffmpeg"), "-hide_banner", "-i", path, "-vn", "-af",
                  f"loudnorm=I={target}:TP={peak}:LRA=7:print_format=json", "-f", "null", "-"])
    # Progress output may follow the JSON. Decode only the measured object.
    start = result.stderr.rfind('{\n')
    if start < 0:
        raise ValueError("loudnorm did not emit a measurement")
    data, _ = json.JSONDecoder().raw_decode(result.stderr[start:])
    return data


def envelope_expression(nodes, default):
    if not nodes:
        return str(default)
    expr = str(nodes[-1][1])
    for (left, gain), (right, end_gain) in reversed(list(zip(nodes, nodes[1:]))):
        linear = f"({gain}+({end_gain}-{gain})*(t-{left})/({right}-{left}))"
        expr = f"if(lt(t,{right}),{linear},{expr})"
    return f"if(lt(t,{nodes[0][0]}),{nodes[0][1]},{expr})"


def mix(project, root, output):
    output = Path(output)
    if output.exists():
        raise ValueError("Mix output exists; choose a new version filename")
    output.parent.mkdir(parents=True, exist_ok=True)
    _, frames = timing(project)
    duration = frames / project["profile"]["fps"]
    cues = project.get("audio_cues", [])
    if not cues:
        raise ValueError("No audio cues; supply narration/original/music explicitly")
    cmd = [binary("ffmpeg"), "-v", "error", "-filter_complex_threads", "1"]
    graph, labels = [], []
    for i, cue in enumerate(cues):
        cmd += ["-i", media_path(root, project["assets"][cue["asset_id"]]["path"])]
        label = f"a{i}"
        gain = envelope_expression(cue.get("envelope", []), cue.get("gain_db", 0))
        filters = [f"atrim=start={cue.get('source_in', 0)}:duration={cue['duration']}",
                   "asetpts=PTS-STARTPTS", "aresample=48000",
                   "aformat=sample_fmts=fltp:channel_layouts=stereo",
                   f"volume='pow(10,({gain})/20)':eval=frame"]
        if cue.get("fade_in"):
            filters.append(f"afade=t=in:st=0:d={cue['fade_in']}")
        if cue.get("fade_out"):
            filters.append(f"afade=t=out:st={cue['duration']-cue['fade_out']}:d={cue['fade_out']}")
        filters.append(f"adelay={round(cue['start'] * 1000)}:all=1")
        graph.append(f"[{i}:a]" + ",".join(filters) + f"[{label}]")
        labels.append(f"[{label}]")
    graph.append("".join(labels) + f"amix=inputs={len(cues)}:normalize=0:dropout_transition=0,apad,atrim=duration={duration}[mix]")
    raw = output.with_name(output.stem + ".premaster.wav")
    if raw.exists():
        raise ValueError("Premaster output exists; preserve it and choose a new version")
    run(cmd + ["-filter_complex", ";".join(graph), "-map", "[mix]", "-c:a", "pcm_f32le", "-n", raw])
    config = project.get("audio_profile", {})
    target, peak = config.get("target_lufs", -16), config.get("true_peak", -2)
    measured = measurement(raw, target, peak)
    if measured["input_i"] in ("-inf", "inf"):
        raise ValueError("Premaster is silent; loudness normalization refused")
    values = {"measured_I": measured["input_i"], "measured_TP": measured["input_tp"],
              "measured_LRA": measured["input_lra"], "measured_thresh": measured["input_thresh"],
              "offset": measured["target_offset"]}
    filt = f"loudnorm=I={target}:TP={peak}:LRA=7:linear=true:" + ":".join(f"{k}={v}" for k, v in values.items())
    run([binary("ffmpeg"), "-v", "error", "-i", raw, "-af", filt, "-ar", "48000", "-ac", "2",
         "-t", str(duration), "-c:a", "pcm_s24le", "-n", output])
    final = measurement(output, target, peak)
    report = {"first_pass": measured, "master_measured": final, "target_lufs": target,
              "target_peak": peak, "listening_review": "not_reviewed", "music_emotional_review": "not_reviewed"}
    write_json(output.with_suffix(".mix.json"), report)
    return report
