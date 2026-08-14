from __future__ import annotations

import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from .paths import config_path, watcher_home


def ensure_home() -> Path:
    root = watcher_home()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def load_config() -> dict[str, Any]:
    ensure_home()
    path = config_path()
    if not path.exists():
        value = {"schema_version": 2, "retention_days": 180, "projects": []}
        atomic_json(path, value)
        return value
    return json.loads(path.read_text(encoding="utf-8"))


def save_config(value: dict[str, Any]) -> None:
    atomic_json(config_path(), value)


def append_jsonl(path: Path, value: dict[str, Any], unique_key: str | None = None) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        if unique_key and any(json.loads(line).get(unique_key) == value.get(unique_key) for line in handle if line.strip()):
            return False
        handle.seek(0, os.SEEK_END)
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(path, 0o600)
    return True


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rewrite_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for value in values:
                handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush(); os.fsync(handle.fileno())
        os.chmod(name, 0o600); os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)
