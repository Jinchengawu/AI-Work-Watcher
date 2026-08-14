from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import repo_root
from .store import ensure_home

MARKER_START = "<!-- AI-WORK-WATCHER:START -->"
MARKER_END = "<!-- AI-WORK-WATCHER:END -->"
HOOK_TAG = "ai-work-watcher-session-end"
BOOTSTRAP = f"""{MARKER_START}
## AI-Work-Watcher

For explicitly registered projects, use `$ai-work-watcher` to prepare and finish development tasks. Do not modify project assets before the user approves a concrete proposal.
{MARKER_END}"""


def _backup(path: Path) -> None:
    if path.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        shutil.copy2(path, path.with_name(f"{path.name}.ai-work-watcher-backup-{stamp}"))


def _replace_marker(path: Path, block: str | None) -> None:
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    start, end = original.find(MARKER_START), original.find(MARKER_END)
    if start >= 0 and end >= start:
        original = original[:start].rstrip() + original[end + len(MARKER_END):].lstrip("\n")
    updated = original.rstrip()
    if block:
        updated = f"{updated}\n\n{block}" if updated else block
    updated = updated.rstrip() + "\n" if updated else ""
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if current != updated:
        path.parent.mkdir(parents=True, exist_ok=True)
        _backup(path)
        path.write_text(updated, encoding="utf-8")


def _hook(path: Path, command: str, remove: bool = False) -> None:
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    hooks = data.setdefault("hooks", {})
    entries = hooks.setdefault("SessionEnd", [])
    entries = [entry for entry in entries if not any(x.get("statusMessage") == HOOK_TAG for x in entry.get("hooks", []))]
    if not remove:
        entries.append({"hooks": [{"type": "command", "command": command, "timeout": 3, "statusMessage": HOOK_TAG}]})
    if entries:
        hooks["SessionEnd"] = entries
    else:
        hooks.pop("SessionEnd", None)
    if not hooks:
        data.pop("hooks", None)
    updated = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if current != updated:
        path.parent.mkdir(parents=True, exist_ok=True)
        _backup(path)
        path.write_text(updated, encoding="utf-8")


def _link(source: Path, destination: Path, force: bool) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink() and destination.resolve() == source.resolve():
        return
    if destination.exists() or destination.is_symlink():
        if not force:
            raise ValueError(f"refusing to replace existing path: {destination}")
        destination.rename(destination.with_name(destination.name + ".ai-work-watcher-backup"))
    destination.symlink_to(source)


def install(force: bool = False) -> list[str]:
    ensure_home()
    root = repo_root()
    source_skill = root / ".agents/skills/ai-work-watcher"
    if not source_skill.is_dir():
        source_skill = Path(__file__).resolve().parent / "skill"
    destinations = [Path.home() / ".agents/skills/ai-work-watcher", Path.home() / ".claude/skills/ai-work-watcher"]
    for destination in destinations:
        _link(source_skill, destination, force)
    binary = Path.home() / ".local/bin/ai-work-watcher"
    source_binary = root / "bin/ai-work-watcher"
    if not source_binary.is_file():
        resolved = shutil.which("ai-work-watcher")
        if not resolved:
            raise ValueError("installed ai-work-watcher console script was not found")
        source_binary = Path(resolved)
    _link(source_binary, binary, force)
    _replace_marker(Path.home() / ".codex/AGENTS.md", BOOTSTRAP)
    _replace_marker(Path.home() / ".claude/CLAUDE.md", BOOTSTRAP)
    _hook(Path.home() / ".codex/hooks.json", f"{binary} hook codex")
    _hook(Path.home() / ".claude/settings.json", f"{binary} hook claude")
    return [str(path) for path in (*destinations, binary)]


def uninstall(purge_data: bool = False) -> list[str]:
    removed = []
    for path in (Path.home() / ".agents/skills/ai-work-watcher", Path.home() / ".claude/skills/ai-work-watcher",
                 Path.home() / ".local/bin/ai-work-watcher"):
        if path.is_symlink():
            path.unlink(); removed.append(str(path))
    _replace_marker(Path.home() / ".codex/AGENTS.md", None)
    _replace_marker(Path.home() / ".claude/CLAUDE.md", None)
    for path in (Path.home() / ".codex/hooks.json", Path.home() / ".claude/settings.json"):
        if path.exists(): _hook(path, "", True)
    if purge_data:
        from .paths import watcher_home
        if watcher_home().exists(): shutil.rmtree(watcher_home()); removed.append(str(watcher_home()))
    return removed


def doctor() -> list[dict[str, Any]]:
    binary_ok = (Path.home() / ".local/bin/ai-work-watcher").is_symlink()
    checks = [{"host": "core", "status": "ok" if binary_ok else "fail", "label": "CLI linked"}]
    for host, command, skill, bootstrap in (
        ("codex", "codex", Path.home() / ".agents/skills/ai-work-watcher", Path.home() / ".codex/AGENTS.md"),
        ("claude", "claude", Path.home() / ".claude/skills/ai-work-watcher", Path.home() / ".claude/CLAUDE.md")):
        available = shutil.which(command) is not None
        integrated = skill.is_symlink() and bootstrap.exists() and MARKER_START in bootstrap.read_text(encoding="utf-8")
        checks.append({"host": host, "status": "ok" if available and integrated else ("skip" if not available else "fail"),
                       "label": "integrated" if integrated else "not integrated"})
    return checks
