from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from .store import load_config, save_config


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result[:40] or "project"


def add_project(path_value: str, name: str | None = None, project_id: str | None = None,
                sensitivity: str = "standard", provider: str = "auto") -> dict[str, Any]:
    path = Path(path_value).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"project path is not a directory: {path}")
    if sensitivity not in {"standard", "sensitive"}:
        raise ValueError("sensitivity must be standard or sensitive")
    if provider not in {"auto", "codex", "claude"}:
        raise ValueError("provider must be auto, codex, or claude")
    config = load_config()
    for existing in config["projects"]:
        if Path(existing["path"]).resolve() == path:
            return existing
    suffix = hashlib.sha256(str(path).encode()).hexdigest()[:8]
    identifier = project_id or f"{_slug(name or path.name)}-{suffix}"
    if any(project["id"] == identifier for project in config["projects"]):
        raise ValueError(f"project id already exists: {identifier}")
    project = {
        "id": identifier,
        "name": name or path.name,
        "path": str(path),
        "enabled": True,
        "sensitivity": sensitivity,
        "provider": provider,
        "exclude_globs": [".git/**", ".env*", "**/secrets/**"],
    }
    config["projects"].append(project)
    save_config(config)
    return project


def remove_project(identifier: str) -> dict[str, Any]:
    config = load_config()
    for index, project in enumerate(config["projects"]):
        if project["id"] == identifier:
            removed = config["projects"].pop(index)
            save_config(config)
            return removed
    raise ValueError(f"unknown project: {identifier}")


def resolve_project(path_value: str | None = None, identifier: str | None = None) -> dict[str, Any] | None:
    config = load_config()
    if identifier:
        return next((project for project in config["projects"] if project["id"] == identifier and project.get("enabled", True)), None)
    candidate = Path(path_value or Path.cwd()).expanduser().resolve()
    matches: list[tuple[int, dict[str, Any]]] = []
    for project in config["projects"]:
        if not project.get("enabled", True):
            continue
        root = Path(project["path"]).resolve()
        try:
            candidate.relative_to(root)
            matches.append((len(root.parts), project))
        except ValueError:
            continue
    return max(matches, key=lambda item: item[0])[1] if matches else None
