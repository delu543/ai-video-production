#!/usr/bin/env python3
"""Offline package audit: links, placeholders, personal paths, media, secrets."""
from pathlib import Path
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".git", "__pycache__", ".qa", ".venv"}
errors = []
SENSITIVE = r"/Users/[^\s'\"]+|gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{32,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
for path in sorted(ROOT.rglob("*")):
    if not path.is_file() or any(part in SKIP for part in path.relative_to(ROOT).parts):
        continue
    relative = str(path.relative_to(ROOT))
    if path.suffix.lower() in {".mp4", ".mp3", ".wav", ".mov", ".ttf", ".woff", ".jpg", ".png"}:
        errors.append(f"Unexpected bundled media/font: {relative}")
    if path.stat().st_size > 512 * 1024:
        errors.append(f"Unexpected large file: {relative}")
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append(f"Unexpected binary file: {relative}")
        continue
    if path.name != "audit_repository.py":
        if re.search(SENSITIVE, text) or re.search(r"/home/(?!runner/)[^\s'\"]+", text):
            errors.append(f"Personal path or credential-shaped content: {relative}")
    if path.suffix == ".md":
        if re.search(r"\[TODO|REPLACE_ME|PLACEHOLDER", text):
            errors.append(f"Unfinished authoring placeholder: {relative}")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            if "://" in target or target.startswith("#"):
                continue
            local = target.split("#", 1)[0]
            if local and not (path.parent / local).exists():
                errors.append(f"Broken local link in {relative}: {target}")
skill = ROOT / "skills/ai-video-production/SKILL.md"
content = skill.read_text()
if not content.startswith("---\nname: ai-video-production\ndescription:"):
    errors.append("Skill frontmatter missing or inconsistent")
if len(content.splitlines()) > 500:
    errors.append("Skill entrypoint too long; move detail into references")
metadata = (skill.parent / "agents/openai.yaml").read_text()
if "$ai-video-production" not in metadata or "AI 视频制作" not in metadata:
    errors.append("Skill UI metadata does not match invocation/name")
try:
    licenses = json.loads((ROOT / "licensing.json").read_text())
    if licenses["default_license"] != "MIT" or licenses["data_license"] != "CC0-1.0":
        errors.append("Unexpected license identifiers")
    mit = (ROOT / "LICENSE").read_text()
    if not mit.startswith("MIT License\n") or "Copyright (c) 2026 delu543" not in mit:
        errors.append("MIT license header/copyright missing")
    if mit != (skill.parent / "LICENSE").read_text():
        errors.append("Installed-package MIT copy differs from root")
    cc0 = (ROOT / "LICENSES/CC0-1.0.txt").read_bytes()
    if cc0 != (skill.parent / "LICENSES/CC0-1.0.txt").read_bytes():
        errors.append("Installed-package CC0 copy differs from root")
    expected_data = {"skills/ai-video-production/assets/brief.example.json", "skills/ai-video-production/assets/project.example.json"}
    if set(licenses["data_files"]) != expected_data:
        errors.append("CC0 data scope changed: explicit rights review required")
    for name in licenses["data_files"]:
        json.loads((ROOT / name).read_text())
except (OSError, KeyError, ValueError) as exc:
    errors.append(f"License package invalid: {exc}")
if "--history" in sys.argv:
    if not (ROOT / ".git").exists():
        errors.append("History audit needs a Git checkout")
    else:
        objects = subprocess.check_output(["git", "rev-list", "--objects", "--all"], cwd=ROOT, text=True).splitlines()
        scanned = 0
        for entry in objects:
            oid, _, name = entry.partition(" ")
            if subprocess.check_output(["git", "cat-file", "-t", oid], cwd=ROOT, text=True).strip() != "blob":
                continue
            scanned += 1
            size = int(subprocess.check_output(["git", "cat-file", "-s", oid], cwd=ROOT))
            if size > 512 * 1024 or Path(name).suffix.lower() in {".mp4", ".mov", ".mp3", ".wav", ".png", ".jpg"}:
                errors.append(f"History contains unexpected large/media blob: {oid[:12]} {name}")
                continue
            raw = subprocess.check_output(["git", "cat-file", "blob", oid], cwd=ROOT)
            try:
                historical = raw.decode("utf-8")
            except UnicodeDecodeError:
                errors.append(f"History contains unexpected binary: {oid[:12]} {name}")
                continue
            if Path(name).name != "audit_repository.py" and re.search(SENSITIVE, historical):
                errors.append(f"History contains sensitive-shaped content: {oid[:12]} {name}")
        print(f"History audit: inspected {scanned} blobs across all local refs")
for error in errors:
    print(error)
print(f"Repository audit: {'FAILED' if errors else 'PASSED'} ({len(errors)} issues)")
sys.exit(bool(errors))
