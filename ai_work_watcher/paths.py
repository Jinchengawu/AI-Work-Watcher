from __future__ import annotations

import os
from pathlib import Path


def watcher_home() -> Path:
    return Path(os.environ.get("AI_WORK_WATCHER_HOME", Path.home() / ".ai-work-watcher")).expanduser()


def config_path() -> Path:
    return watcher_home() / "config.json"


def project_private_dir(project_id: str) -> Path:
    return watcher_home() / "projects" / project_id


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]
