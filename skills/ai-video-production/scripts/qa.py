"""Objective export audit. Subjective gates deliberately remain not_reviewed."""
from fractions import Fraction
from pathlib import Path
from audio import measurement
from core import binary, probe, run, sha256, timing, write_json


def audit(project, path, report):
    meta = probe(path, count=True)
    streams = meta["streams"]
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    sound = next((s for s in streams if s.get("codec_type") == "audio"), None)
    errors = []
    p = project["profile"]
    _, frames = timing(project)
    if not video or not sound:
        raise ValueError("Expected both picture and audio streams")
    if (video["width"], video["height"]) != (p["width"], p["height"]):
        errors.append("Dimensions mismatch")
    if Fraction(video["avg_frame_rate"]) != p["fps"]:
        errors.append("Average frame rate mismatch")
    if int(video["nb_read_frames"]) != frames:
        errors.append("Frame count mismatch")
    if video.get("sample_aspect_ratio") != "1:1":
        errors.append("SAR must be 1:1")
    if video.get("codec_name") != "h264" or video.get("pix_fmt") != "yuv420p":
        errors.append("Expected H.264/yuv420p")
    if sound.get("codec_name") != "aac" or sound.get("sample_rate") != "48000":
        errors.append("Expected AAC/48kHz")
    if sound.get("channels") != 2:
        errors.append("Expected stereo")
    expected = frames / p["fps"]
    for stream in (video, sound):
        if abs(float(stream.get("duration", expected))-expected) > .1:
            errors.append("Stream duration differs from timeline")
    # Full decode catches truncated/corrupt exports that metadata alone would accept.
    run([binary("ffmpeg"), "-v", "error", "-i", path, "-f", "null", "-"])
    audio = measurement(path)
    target = project.get("audio_profile", {}).get("target_lufs", -16)
    actual_lufs, true_peak = float(audio["input_i"]), float(audio["input_tp"])
    if abs(actual_lufs-target) > 1:
        errors.append("Integrated loudness differs by more than 1 LU")
    if true_peak > project.get("audio_profile", {}).get("delivery_true_peak", -1.5):
        errors.append("Final encoded true peak exceeds delivery target")
    data = {"ok": not errors, "errors": errors, "sha256": sha256(path), "expected_frames": frames,
            "metadata": meta, "loudness": audio, "full_decode": "passed",
            "editorial_review": "not_reviewed", "visual_review": "not_reviewed",
            "continuity_review": "not_reviewed", "listening_review": "not_reviewed",
            "rights_review": "not_reviewed", "user_acceptance": "not_assumed"}
    write_json(report, data)
    return data


def review_frames(project, path, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    rows, _ = timing(project)
    times = set()
    for row in rows:
        times.update((row["start"]+.05, (row["start"]+row["end"])/2, max(row["start"], row["end"]-.1)))
        if row["incoming"]:
            times.add(row["start"] + row["incoming"] / project["profile"]["fps"] / 2)
    for i, seconds in enumerate(sorted(times)):
        out = directory / f"{i:04d}-{seconds:.3f}.png"
        if not out.exists():
            run([binary("ffmpeg"), "-v", "error", "-ss", str(seconds), "-i", path,
                 "-frames:v", "1", "-vf", "scale=960:-2", "-n", out])
    return {"directory": str(directory), "frames": len(times), "motion_and_listening_review": "still_required"}
