from __future__ import annotations

import fnmatch
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import watcher_home
from .store import append_jsonl, read_jsonl

DEFAULT_IGNORES = (".git/**", ".env", ".env.*", "**/.env", "**/.env.*", "node_modules/**",
                   "vendor/**", ".venv/**", "venv/**", "dist/**", "build/**", "**/__pycache__/**",
                   "*.key", "*.pem", "*.p12")
CONTEXT_NAMES = {"README.md", "README.zh-CN.md", "AGENTS.md", "CLAUDE.md", "pyproject.toml",
                 "package.json", "Cargo.toml", "go.mod", "Makefile", "manifest.json"}


def snapshot_path(project_id: str) -> Path:
    return watcher_home() / "snapshots" / f"{project_id}.jsonl"


def _ignored(relative: str, extra: list[str]) -> bool:
    return any(fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(relative + "/", pattern)
               for pattern in (*DEFAULT_IGNORES, *extra))


def _kind(relative: str) -> str:
    name = Path(relative).name
    if name in {"AGENTS.md", "CLAUDE.md"}:
        return "agent_instruction"
    if name.startswith("README"):
        return "readme"
    if "skill" in relative.lower():
        return "skill"
    if name in {"pyproject.toml", "package.json", "Cargo.toml", "go.mod", "manifest.json"}:
        return "manifest"
    if "test" in relative.lower() and Path(relative).suffix in {".toml", ".json", ".yaml", ".yml"}:
        return "test_config"
    return "context"


def capture_snapshot(project: dict[str, Any]) -> dict[str, Any]:
    root = Path(project["path"])
    gitignore = root / ".gitignore"
    ignored_by_project = []
    if gitignore.exists():
        ignored_by_project = [line.strip().lstrip("/") for line in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines()
                              if line.strip() and not line.lstrip().startswith(("#", "!"))]
        ignored_by_project += [f"{pattern}/**" for pattern in ignored_by_project if not any(char in pattern for char in "*?[")]
    exclusions = [*project.get("exclude", []), *ignored_by_project]
    entries = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if _ignored(relative, exclusions):
            continue
        if not (path.name in CONTEXT_NAMES or relative.startswith((".agents/skills/", ".ai-work-watcher/", "docs/"))):
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append({"path": relative, "kind": _kind(relative), "sha256": digest})
    history = read_jsonl(snapshot_path(project["id"]))
    previous = {item["path"]: item["sha256"] for item in history[-1]["entries"]} if history else {}
    current = {item["path"]: item["sha256"] for item in entries}
    drift = {"added": sorted(current.keys() - previous.keys()), "removed": sorted(previous.keys() - current.keys()),
             "changed": sorted(key for key in current.keys() & previous.keys() if current[key] != previous[key])}
    project_type = "python" if (root / "pyproject.toml").exists() else ("node" if (root / "package.json").exists() else
                   ("rust" if (root / "Cargo.toml").exists() else ("go" if (root / "go.mod").exists() else "unknown")))
    record = {"schema_version": 1, "project_id": project["id"], "project_type": project_type,
              "timestamp": datetime.now(timezone.utc).isoformat(),
              "top_level": sorted(path.name for path in root.iterdir() if not _ignored(path.name, exclusions)),
              "entries": entries, "drift": drift}
    append_jsonl(snapshot_path(project["id"]), record)
    return record
