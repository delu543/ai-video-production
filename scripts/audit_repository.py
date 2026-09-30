#!/usr/bin/env python3
"""Offline package audit: links, placeholders, personal paths, media, secrets."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".git", "__pycache__", ".qa", ".venv"}
errors = []
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
        if re.search(r"/Users/[^\s'\"]+|/home/[^\s'\"]+|gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{32,}", text):
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
for error in errors:
    print(error)
print(f"Repository audit: {'FAILED' if errors else 'PASSED'} ({len(errors)} issues)")
sys.exit(bool(errors))
