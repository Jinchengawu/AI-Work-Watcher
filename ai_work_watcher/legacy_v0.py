from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import watcher_home
from .store import atomic_json, load_config, save_config

OLD_START = "<!-- WATER-SUPERVISOR:START -->"
OLD_END = "<!-- WATER-SUPERVISOR:END -->"


def _strip(path: Path) -> None:
    if not path.exists(): return
    text = path.read_text(encoding="utf-8")
    start, end = text.find(OLD_START), text.find(OLD_END)
    if start >= 0 and end >= start:
        path.write_text((text[:start].rstrip() + "\n" + text[end + len(OLD_END):].lstrip("\n")).strip() + "\n", encoding="utf-8")


def _strip_hook(path: Path) -> None:
    if not path.exists(): return
    try: data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError: return
    hooks = data.get("hooks", {})
    entries = hooks.get("SessionEnd", [])
    kept = [entry for entry in entries if not any(item.get("statusMessage") == "water-supervisor-session-end"
            for item in entry.get("hooks", []))]
    if kept: hooks["SessionEnd"] = kept
    else: hooks.pop("SessionEnd", None)
    if not hooks: data.pop("hooks", None)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def migrate_legacy_v0() -> dict[str, Any]:
    marker = watcher_home() / "migrations/legacy-v0.json"
    if marker.exists():
        return {"status": "already_migrated", **json.loads(marker.read_text(encoding="utf-8"))}
    old_home = Path(os.environ.get("AI_WORK_WATCHER_LEGACY_HOME", Path.home() / ".water"))
    archive = watcher_home() / "archive/legacy-v0"
    archive.mkdir(parents=True, exist_ok=True)
    if old_home.exists():
        for item in old_home.iterdir():
            target = archive / item.name
            if not target.exists():
                shutil.copytree(item, target) if item.is_dir() else shutil.copy2(item, target)
    old_config = old_home / "config.json"
    imported = 0
    if old_config.exists():
        legacy = json.loads(old_config.read_text(encoding="utf-8"))
        config = load_config()
        for old in legacy.get("projects", []):
            if not any(item["path"] == old.get("path") for item in config["projects"]):
                config["projects"].append({"id": old.get("id"), "name": old.get("name"), "path": old.get("path"),
                    "provider": old.get("provider", "auto"), "exclude": []}); imported += 1
        save_config(config)
    for path in (Path.home() / ".agents/skills/water-supervisor", Path.home() / ".claude/skills/water-supervisor",
                 Path.home() / ".local/bin/waterctl"):
        if path.is_symlink(): path.unlink()
    for path in (Path.home() / ".codex/AGENTS.md", Path.home() / ".claude/CLAUDE.md"): _strip(path)
    for path in (Path.home() / ".codex/hooks.json", Path.home() / ".claude/settings.json"): _strip_hook(path)
    launch = Path.home() / "Library/LaunchAgents/com.water-supervisor.weekly.plist"
    if launch.exists(): launch.unlink()
    if old_home.exists(): shutil.rmtree(old_home)
    result = {"migrated_at": datetime.now(timezone.utc).isoformat(), "projects_imported": imported,
              "archive": str(archive)}
    atomic_json(marker, result)
    return {"status": "migrated", **result}
