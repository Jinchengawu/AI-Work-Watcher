from __future__ import annotations

import os
from pathlib import Path


def water_home() -> Path:
    override = os.environ.get("WATER_HOME")
    return Path(override).expanduser().resolve() if override else Path.home() / ".water"


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    return water_home() / "config.json"


def recommendations_path() -> Path:
    return water_home() / "recommendations.jsonl"


def guidance_path() -> Path:
    return water_home() / "guidance" / "accepted.md"
