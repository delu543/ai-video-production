#!/usr/bin/env python3
"""Install a portable Skill; preserve existing content and versioned backups."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

SOURCE = Path(__file__).resolve().parent.parent / "skills" / "ai-video-production"


def inventory(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()
            and "__pycache__" not in p.parts and p.name != ".installation.json"}


def install(destination, update=False):
    dest = Path(destination).expanduser().resolve()
    source_hashes = inventory(SOURCE)
    if dest.exists():
        current = inventory(dest)
        if current == source_hashes:
            return {"status": "already_current", "path": str(dest)}
        metadata = dest / ".installation.json"
        if not update:
            raise ValueError("Existing different Skill preserved; use --update only for an installed, unchanged version")
        if not metadata.exists() or current != json.loads(metadata.read_text())["files"]:
            raise ValueError("Unmanaged or locally modified Skill; merge changes manually before update")
        backup = dest.parent / ".ai-video-production-backups" / str(time.time_ns())
        backup.parent.mkdir(parents=True, exist_ok=True)
        dest.rename(backup)
    else:
        backup = None
    try:
        shutil.copytree(SOURCE, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (dest / ".installation.json").write_text(json.dumps({"files": source_hashes}, indent=2)+"\n")
    except Exception:
        # Never erase incomplete output; preserve and tell caller how to restore the backup.
        raise ValueError(f"Install failed; partial files retained at {dest}; previous version at {backup}")
    return {"status": "installed", "path": str(dest), "backup": str(backup) if backup else None}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--destination", default="~/.codex/skills/ai-video-production")
    p.add_argument("--update", action="store_true")
    args = p.parse_args()
    try:
        print(json.dumps(install(args.destination, args.update), ensure_ascii=False, indent=2))
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
