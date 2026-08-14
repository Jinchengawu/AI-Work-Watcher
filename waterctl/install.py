from __future__ import annotations

import json
import os
import plistlib
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import repo_root, water_home
from .store import ensure_home


MARKER_START = "<!-- WATER-SUPERVISOR:START -->"
MARKER_END = "<!-- WATER-SUPERVISOR:END -->"
BOOTSTRAP = f"""{MARKER_START}
## Water Supervisor

For explicitly registered projects, use `$water-supervisor` throughout development work. Read accepted guidance at `~/.water/guidance/accepted.md` before planning. Before the final response, record a concise structured session summary with `waterctl record --stdin`. Water is read-only toward supervised projects: propose improvements, never apply them without explicit user authorization.
{MARKER_END}"""
HOOK_TAG = "water-supervisor-session-end"


def _backup(path: Path) -> None:
    if path.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        shutil.copy2(path, path.with_name(f"{path.name}.water-backup-{stamp}"))


def _replace_marker(path: Path, block: str | None) -> None:
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    start = original.find(MARKER_START)
    end = original.find(MARKER_END)
    if start >= 0 and end >= start:
        end += len(MARKER_END)
        original = original[:start].rstrip() + original[end:].lstrip("\n")
    updated = original.rstrip()
    if block:
        updated = f"{updated}\n\n{block}" if updated else block
    updated = updated.rstrip() + "\n" if updated else ""
    if updated != (path.read_text(encoding="utf-8") if path.exists() else ""):
        path.parent.mkdir(parents=True, exist_ok=True)
        _backup(path)
        path.write_text(updated, encoding="utf-8")


def _owned_hook(command: str) -> dict[str, Any]:
    return {"hooks": [{"type": "command", "command": command, "timeout": 3, "statusMessage": HOOK_TAG}]}


def _merge_hook(path: Path, command: str, remove: bool = False) -> None:
    data: dict[str, Any] = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    hooks = data.setdefault("hooks", {})
    entries = hooks.setdefault("SessionEnd", [])
    kept = [entry for entry in entries if not any(handler.get("statusMessage") == HOOK_TAG for handler in entry.get("hooks", []))]
    if not remove:
        kept.append(_owned_hook(command))
    if kept:
        hooks["SessionEnd"] = kept
    else:
        hooks.pop("SessionEnd", None)
    if not hooks:
        data.pop("hooks", None)
    updated = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    if updated != original:
        path.parent.mkdir(parents=True, exist_ok=True)
        _backup(path)
        path.write_text(updated, encoding="utf-8")


def _symlink(source: Path, destination: Path, force: bool = False) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink() and destination.resolve() == source.resolve():
        return
    if destination.exists() or destination.is_symlink():
        if not force:
            raise ValueError(f"refusing to replace existing path: {destination}")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = destination.with_name(f"{destination.name}.water-backup-{stamp}")
        destination.rename(backup)
    destination.symlink_to(source)


def _launch_agent(bin_path: Path) -> dict[str, Any]:
    log_dir = water_home() / "logs"
    return {
        "Label": "com.water-supervisor.weekly",
        "ProgramArguments": [str(bin_path), "review", "weekly", "--provider", "auto"],
        "EnvironmentVariables": {"WATER_INTERNAL_RUN": "1", "TZ": "Asia/Shanghai"},
        "StartCalendarInterval": {"Weekday": 2, "Hour": 9, "Minute": 0},
        "StandardOutPath": str(log_dir / "weekly.out.log"),
        "StandardErrorPath": str(log_dir / "weekly.err.log"),
        "RunAtLoad": False,
    }


def _activate_launch_agent(path: Path) -> None:
    executable = shutil.which("launchctl")
    if not executable:
        raise ValueError("launchctl is required to activate the weekly schedule")
    domain = f"gui/{os.getuid()}"
    service = f"{domain}/com.water-supervisor.weekly"
    subprocess.run([executable, "bootout", service], capture_output=True, text=True)
    result = subprocess.run([executable, "bootstrap", domain, str(path)], capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError(f"failed to activate weekly schedule: {result.stderr.strip()}")


def install(force: bool = False, schedule: bool = True) -> list[str]:
    ensure_home()
    root = repo_root()
    source_skill = root / ".agents" / "skills" / "water-supervisor"
    source_bin = root / "bin" / "waterctl"
    destinations = [
        Path.home() / ".agents" / "skills" / "water-supervisor",
        Path.home() / ".claude" / "skills" / "water-supervisor",
    ]
    for destination in destinations:
        _symlink(source_skill, destination, force)
    bin_link = Path.home() / ".local" / "bin" / "waterctl"
    _symlink(source_bin, bin_link, force)
    _replace_marker(Path.home() / ".codex" / "AGENTS.md", BOOTSTRAP)
    _replace_marker(Path.home() / ".claude" / "CLAUDE.md", BOOTSTRAP)
    _merge_hook(Path.home() / ".codex" / "hooks.json", f"{bin_link} hook codex")
    _merge_hook(Path.home() / ".claude" / "settings.json", f"{bin_link} hook claude")
    if schedule:
        agent_path = Path.home() / "Library" / "LaunchAgents" / "com.water-supervisor.weekly.plist"
        agent_path.parent.mkdir(parents=True, exist_ok=True)
        desired = plistlib.dumps(_launch_agent(bin_link))
        original = agent_path.read_bytes() if agent_path.exists() else b""
        if original != desired:
            _backup(agent_path)
            agent_path.write_bytes(desired)
        _activate_launch_agent(agent_path)
    return [str(path) for path in [*destinations, bin_link]]


def uninstall(purge_data: bool = False) -> list[str]:
    root = repo_root()
    removed = []
    for path in (
        Path.home() / ".agents" / "skills" / "water-supervisor",
        Path.home() / ".claude" / "skills" / "water-supervisor",
        Path.home() / ".local" / "bin" / "waterctl",
    ):
        if path.is_symlink() and path.resolve() in {root / ".agents" / "skills" / "water-supervisor", root / "bin" / "waterctl"}:
            path.unlink()
            removed.append(str(path))
    _replace_marker(Path.home() / ".codex" / "AGENTS.md", None)
    _replace_marker(Path.home() / ".claude" / "CLAUDE.md", None)
    for path in (Path.home() / ".codex" / "hooks.json", Path.home() / ".claude" / "settings.json"):
        if path.exists():
            _merge_hook(path, "", remove=True)
    agent_path = Path.home() / "Library" / "LaunchAgents" / "com.water-supervisor.weekly.plist"
    if agent_path.exists():
        executable = shutil.which("launchctl")
        if executable:
            subprocess.run(
                [executable, "bootout", f"gui/{os.getuid()}/com.water-supervisor.weekly"],
                capture_output=True,
                text=True,
            )
        agent_path.unlink()
        removed.append(str(agent_path))
    if purge_data and water_home().exists():
        shutil.rmtree(water_home())
        removed.append(str(water_home()))
    return removed


def doctor() -> list[tuple[bool, str]]:
    root = repo_root()
    checks = [
        (shutil.which("codex") is not None, "Codex CLI available"),
        (shutil.which("claude") is not None, "Claude Code available"),
        ((Path.home() / ".agents" / "skills" / "water-supervisor").is_symlink(), "Codex skill linked"),
        ((Path.home() / ".claude" / "skills" / "water-supervisor").is_symlink(), "Claude skill linked"),
        ((Path.home() / ".local" / "bin" / "waterctl").resolve() == root / "bin" / "waterctl", "waterctl linked"),
        ((Path.home() / "Library" / "LaunchAgents" / "com.water-supervisor.weekly.plist").exists(), "weekly schedule installed"),
    ]
    for path, label in ((Path.home() / ".codex" / "AGENTS.md", "Codex bootstrap installed"), (Path.home() / ".claude" / "CLAUDE.md", "Claude bootstrap installed")):
        checks.append((path.exists() and MARKER_START in path.read_text(encoding="utf-8"), label))
    return checks
