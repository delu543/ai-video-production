#!/usr/bin/env python3
"""CLI for the reusable real-footage workflow. The only paid path is `voice`, gated by the cost ledger; no downloads."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from core import binary, read_json, run, validate, write_json, VERSION


def init_project(directory):
    root = Path(directory)
    if root.exists() and any(root.iterdir()):
        raise ValueError("Target is not empty; preserve existing project")
    root.mkdir(parents=True, exist_ok=True)
    for name in ("assets", "audio", "work", "deliverables"):
        (root / name).mkdir(exist_ok=True)
    template = Path(__file__).resolve().parent.parent / "assets"
    shutil.copyfile(template / "brief.example.json", root / "brief.json")
    shutil.copyfile(template / "review-checklist.md", root / "review-checklist.md")
    project = read_json(template / "project.example.json")
    # Example is a schema guide, never a production script or approved source.
    for name in ("facts", "beats", "shots", "captions", "audio_cues"):
        project[name] = []
    project["assets"] = {}
    project["title"] = ""
    write_json(root / "project.json", project)
    write_json(root / "state.json", {"status": "intake", "latest_request": "", "owner": "",
                                    "verified": [], "pending": ["research", "design", "voice", "edit", "qa"],
                                    "blockers": [], "next_action": "Complete brief and research"})
    write_json(root / "costs.json", {"currency": "CNY", "entries": []})
    return {"project": str(root.resolve()), "next": "Populate brief/project; an empty init is not renderable"}


def doctor():
    result = {"workflow_version": VERSION, "python": sys.version.split()[0], "tools": {}}
    for tool in ("ffmpeg", "ffprobe"):
        try:
            path = binary(tool)
            result["tools"][tool] = {"available": True, "path": path,
                                      "version": run([path, "-version"]).stdout.splitlines()[0]}
        except ValueError as exc:
            result["tools"][tool] = {"available": False, "reason": str(exc)}
    if result["tools"]["ffmpeg"]["available"]:
        filters = run([binary("ffmpeg"), "-hide_banner", "-filters"]).stdout
        result["required_filters"] = {name: name in filters for name in ("ass", "blend", "loudnorm", "gblur", "amix")}
    from tts import KEY_FILE
    result["tts"] = {"minimax_key_configured": bool(os.environ.get("MINIMAX_API_KEY") or KEY_FILE.is_file()),
                     "note": "`voice` reserves budget before each paid line; other ASR/browser tools are external"}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    start = commands.add_parser("init")
    start.add_argument("directory")
    voices = commands.add_parser("voice-list", help="List MiniMax system voices (free)")
    voices.add_argument("--contains", default="")
    voices.add_argument("--region", choices=("auto", "global", "cn"), default="auto")
    for name in ("check", "captions", "mix", "render", "qa", "review-frames", "reserve", "settle", "voice"):
        sub = commands.add_parser(name)
        sub.add_argument("project", help="Canonical project.json")
        if name in ("check", "mix", "render"):
            sub.add_argument("--allow-test-assets", action="store_true", help="Synthetic test fixtures only; never production")
        if name == "check":
            sub.add_argument("--stage", choices=("design", "render", "publish"), default="design")
        if name in ("captions", "mix", "render", "qa", "review-frames"):
            sub.add_argument("output", help="File, or directory for captions/review-frames")
        if name in ("qa", "review-frames"):
            sub.add_argument("video")
        if name == "reserve":
            sub.add_argument("--id", required=True)
            sub.add_argument("--provider", required=True)
            sub.add_argument("--fingerprint", required=True)
            sub.add_argument("--maximum", type=float, required=True)
            sub.add_argument("--pricing-basis", required=True)
        if name == "voice":
            sub.add_argument("--voice", required=True, help="Provider voice_id chosen after a short sample")
            sub.add_argument("--model", default="speech-2.8-hd")
            sub.add_argument("--speed", type=float, default=1.0)
            sub.add_argument("--language", default="auto", help="Provider language_boost, e.g. Chinese, English")
            sub.add_argument("--beats", default="", help="Comma-separated beat ids; default all narrated beats")
            sub.add_argument("--sample-text", help="Synthesize only this ~10 s sample, not the script")
            sub.add_argument("--price", type=float, required=True, help="Live price per 10k characters in budget currency")
            sub.add_argument("--pricing-basis", required=True, help="Where/when the price was checked")
            sub.add_argument("--region", choices=("auto", "global", "cn"), default="auto")
        if name == "settle":
            sub.add_argument("--id", required=True)
            sub.add_argument("--amount", type=float, required=True)
            sub.add_argument("--response-id", required=True)
            sub.add_argument("--invoice-verified", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = doctor()
        elif args.command == "init":
            result = init_project(args.directory)
        elif args.command == "voice-list":
            from tts import list_voices
            result = {"voices": list_voices(args.region, args.contains)}
        else:
            project_path = Path(args.project).resolve()
            root, project = project_path.parent, read_json(project_path)
            if args.command in ("check", "mix", "render"):
                stage = args.stage if args.command == "check" else "render"
                report = validate(project, root, stage, args.allow_test_assets)
                if not report["ok"] or args.command == "check":
                    print(json.dumps(report, ensure_ascii=False, indent=2))
                    return 0 if report["ok"] else 1
            if args.command == "captions":
                from captions import create
                result = {"files": [str(p) for p in create(project, args.output)]}
            elif args.command == "mix":
                from audio import mix
                result = mix(project, root, args.output)
            elif args.command == "render":
                from render import render
                result = render(project, root, args.output)
            elif args.command == "qa":
                from qa import audit
                result = audit(project, args.video, args.output)
            elif args.command == "review-frames":
                from qa import review_frames
                result = review_frames(project, args.video, args.output)
            elif args.command == "reserve":
                from costs import reserve
                result = reserve(root, project, args.id, args.provider, args.fingerprint, args.maximum, args.pricing_basis)
            elif args.command == "voice":
                from tts import narration_items, synthesize
                items = ([("sample-" + args.voice.replace(" ", "_").replace("/", "_"), args.sample_text)] if args.sample_text
                         else narration_items(project, [b for b in args.beats.split(",") if b]))
                if not items:
                    raise ValueError("No narration to synthesize")
                result = synthesize(root, project, items, args.voice, args.model, args.speed, args.language,
                                    args.price, args.pricing_basis, args.region)
            elif args.command == "settle":
                from costs import settle
                result = settle(root, args.id, args.amount, args.response_id, args.invoice_verified)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok", True) else 1
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
