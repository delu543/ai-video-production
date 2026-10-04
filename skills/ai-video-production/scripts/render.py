"""Frame-counted adjacent dissolves; cached products depend on both neighbours."""
from pathlib import Path
from core import binary, fingerprint, media_path, probe, run, sha256, timing, VERSION
from captions import create


def frame_count(path):
    streams = probe(path, count=True)["streams"]
    return int(next(s for s in streams if s["codec_type"] == "video")["nb_read_frames"])


def encode_args(profile):
    # Intermediates (raw -> core/bridge -> concat) are lossless; profile CRF applies once, at final export.
    return ["-an", "-c:v", "libx264", "-preset", "ultrafast", "-qp", "0",
            "-threads", "2", "-pix_fmt", "yuv420p", "-r", str(profile["fps"]), "-fps_mode", "cfr"]


def checked_render(cmd, output, frames, profile):
    if not output.exists():
        run(cmd + ["-frames:v", str(frames)] + encode_args(profile) + ["-n", output])
    if frame_count(output) != frames:
        raise ValueError(f"{output.name}: expected {frames} frames; incomplete cache is preserved for diagnosis")
    return output


def render(project, root, output):
    root, output = Path(root), Path(output)
    if output.exists():
        raise ValueError("Video output exists; choose a new version filename")
    master = media_path(root, project["master_audio"])
    if not master.is_file():
        raise ValueError("master_audio missing; arrange and mix audio first")
    p = project["profile"]
    rows, total_frames = timing(project)
    fps, width, height = p["fps"], p["width"], p["height"]
    work = root / "work" / "render"
    work.mkdir(parents=True, exist_ok=True)
    # Include code and encoder version, not just manifest; any implementation change invalidates cache.
    engine = fingerprint({"version": VERSION, "code": sha256(Path(__file__)),
                          "ffmpeg": run([binary("ffmpeg"), "-version"]).stdout.splitlines()[0]})
    raw = []
    for shot in rows:
        asset = project["assets"][shot["asset_id"]]
        source = media_path(root, asset["path"])
        key = fingerprint([engine, shot, p, sha256(source)])
        out = work / f"raw-{key}.mp4"
        cmd = [binary("ffmpeg"), "-v", "error", "-filter_complex_threads", "1"]
        if asset["kind"] == "still":
            cmd += ["-loop", "1", "-framerate", str(fps), "-i", source]
        else:
            cmd += ["-ss", str(shot.get("source_in", 0)), "-i", source]
        pre = f"setpts=(PTS-STARTPTS)/{shot.get('speed', 1)},fps={fps},setsar=1"
        if shot.get("crop"):
            w, h, x, y = shot["crop"]
            pre = f"crop={w}:{h}:{x}:{y}," + pre
        cover = f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,crop={width}:{height}"
        if shot.get("framing", "cover") == "contain":
            fg = f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos"
            graph = f"[0:v]{pre},split=2[b0][f0];[b0]{cover},gblur=sigma=35,eq=brightness=-0.035[b];[f0]{fg}[f];[b][f]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p[v]"
        else:
            zoom = shot.get("zoom", 0)
            if zoom:
                z = f"zoompan=z='1+{zoom}*on/{max(1,shot['frames']-1)}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps={fps}"
                graph = f"[0:v]{pre},{cover},{z},format=yuv420p[v]"
            else:
                graph = f"[0:v]{pre},{cover},format=yuv420p[v]"
        raw.append(checked_render(cmd + ["-filter_complex", graph, "-map", "[v]"], out, shot["frames"], p))
    groups = []
    for i, shot in enumerate(rows):
        incoming = shot["incoming"]
        outgoing = rows[i+1]["incoming"] if i+1 < len(rows) else 0
        keep = shot["frames"] - incoming - outgoing
        if keep:
            key = fingerprint([engine, "core", raw[i].name, incoming, outgoing])
            out = work / f"core-{key}.mp4"
            filt = f"trim=start_frame={incoming}:end_frame={shot['frames']-outgoing},setpts=PTS-STARTPTS,fps={fps},setsar=1"
            groups.append(checked_render([binary("ffmpeg"), "-v", "error", "-i", raw[i], "-vf", filt], out, keep, p))
        if outgoing:
            # Left and right hashes are both dependencies, fixing stale left-side transitions.
            key = fingerprint([engine, "bridge", raw[i].name, raw[i+1].name, outgoing])
            out = work / f"bridge-{key}.mp4"
            span = (outgoing - 1) / fps
            graph = (f"[0:v]trim=start_frame={shot['frames']-outgoing},settb=expr=1/{fps},setpts=N[a];"
                     f"[1:v]trim=end_frame={outgoing},settb=expr=1/{fps},setpts=N[b];"
                     f"[a][b]blend=all_expr='A*(1-T/{span})+B*T/{span}',settb=expr=1/{fps},setpts=N,setsar=1[v]")
            groups.append(checked_render([binary("ffmpeg"), "-v", "error", "-filter_complex_threads", "1",
                                          "-i", raw[i], "-i", raw[i+1], "-filter_complex", graph, "-map", "[v]"], out, outgoing, p))
    sequence = work / f"sequence-{fingerprint([g.name for g in groups])}.txt"
    def concat_path(path):
        return str(path.resolve()).replace("'", "'\\''")
    sequence.write_text("\n".join(f"file '{concat_path(g)}'" for g in groups)+"\n", encoding="utf-8")
    picture = work / f"picture-{fingerprint([engine, [g.name for g in groups]])}.mp4"
    if not picture.exists():
        run([binary("ffmpeg"), "-v", "error", "-f", "concat", "-safe", "0", "-i", sequence,
             "-c", "copy", "-n", picture])
    if frame_count(picture) != total_frames:
        raise ValueError("Concatenated picture frame count differs from canonical timeline")
    master_duration = float(probe(master)["format"]["duration"])
    if abs(master_duration - total_frames / fps) > .1:
        raise ValueError("Master duration mismatches picture; align audio before export")
    ass, _ = create(project, work)
    filters = [f"fps={fps}", "setsar=1"]
    if project.get("captions"):
        # Run with cwd at ASS directory: a safe ASCII basename avoids filter-path quoting issues.
        filters.append("ass=filename=captions.ass")
    fade_in = p.get("fade_in", .6)
    fade_out = p.get("fade_out", .8)
    duration = total_frames / fps
    if fade_in:
        filters.append(f"fade=t=in:st=0:d={min(fade_in,duration/3)}")
    if fade_out:
        filters.append(f"fade=t=out:st={duration-min(fade_out,duration/3)}:d={min(fade_out,duration/3)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [binary("ffmpeg"), "-v", "error", "-i", str(picture.resolve()), "-i", str(master),
           "-map", "0:v:0", "-map", "1:a:0", "-vf", ",".join(filters),
           "-c:v", "libx264", "-crf", str(p.get("crf", 18)), "-preset", p.get("preset", "veryfast"),
           "-threads", "2", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2",
           "-frames:v", str(total_frames), "-t", str(duration), "-movflags", "+faststart", "-n", str(output.resolve())]
    import subprocess
    result = subprocess.run(cmd, cwd=ass.parent, capture_output=True, text=True)
    if result.returncode:
        raise ValueError("Final encode failed: " + result.stderr[-4000:])
    if frame_count(output) != total_frames:
        raise ValueError("Final exported frame count mismatch")
    return {"output": str(output), "frames": total_frames, "duration": duration, "sha256": sha256(output)}
