from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .store import load_config, save_config


def _identifier(path: Path) -> str:
    return "prj-" + hashlib.sha256(str(path).encode()).hexdigest()[:12]


def add_project(path: str, name: str | None = None, project_id: str | None = None,
                provider: str = "auto", exclude: list[str] | None = None) -> dict[str, Any]:
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"project path is not a directory: {root}")
    if provider not in {"auto", "codex", "claude"}:
        raise ValueError("provider must be auto, codex, or claude")
    config = load_config()
    for project in config["projects"]:
        if Path(project["path"]).resolve() == root:
            return project
    project = {"id": project_id or _identifier(root), "name": name or root.name,
               "path": str(root), "provider": provider, "exclude": exclude or []}
    if any(item["id"] == project["id"] for item in config["projects"]):
        raise ValueError(f"duplicate project id: {project['id']}")
    config["projects"].append(project)
    save_config(config)
    asset_root = root / ".ai-work-watcher"
    asset_root.mkdir(exist_ok=True)
    project_file = asset_root / "project.md"
    if not project_file.exists():
        project_file.write_text(
            f"# {project['name']}\n\nProject ID: `{project['id']}`\n\n"
            "AI-Work-Watcher assets in this directory require explicit approval.\n",
            encoding="utf-8",
        )
    return project


def remove_project(identifier: str) -> dict[str, Any]:
    config = load_config()
    found = next((item for item in config["projects"] if item["id"] == identifier), None)
    if not found:
        raise ValueError(f"unknown project: {identifier}")
    config["projects"] = [item for item in config["projects"] if item["id"] != identifier]
    save_config(config)
    return found


def resolve_project(cwd: str | None = None, project_id: str | None = None) -> dict[str, Any] | None:
    projects = load_config()["projects"]
    if project_id:
        return next((item for item in projects if item["id"] == project_id), None)
    current = Path(cwd or Path.cwd()).expanduser().resolve()
    matches = []
    for project in projects:
        root = Path(project["path"]).resolve()
        try:
            current.relative_to(root)
            matches.append((len(root.parts), project))
        except ValueError:
            pass
    return max(matches, default=(0, None), key=lambda item: item[0])[1]
