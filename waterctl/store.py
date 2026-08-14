from __future__ import annotations

import fcntl
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .paths import config_path, guidance_path, recommendations_path, water_home


DEFAULT_CONFIG = {
    "schema_version": 1,
    "retention_days": 180,
    "timezone": "Asia/Shanghai",
    "default_provider": "auto",
    "projects": [],
}


def ensure_home() -> Path:
    root = water_home()
    for child in (root, root / "projects", root / "reviews", root / "guidance", root / "logs"):
        child.mkdir(parents=True, exist_ok=True)
    if not config_path().exists():
        write_json_atomic(config_path(), DEFAULT_CONFIG)
    if not guidance_path().exists():
        guidance_path().write_text("# Accepted Water Guidance\n\nNo guidance has been approved yet.\n", encoding="utf-8")
    return root


def load_config() -> dict[str, Any]:
    ensure_home()
    with config_path().open(encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("schema_version") != 1 or not isinstance(data.get("projects"), list):
        raise ValueError("invalid Water config")
    return data


def save_config(data: dict[str, Any]) -> None:
    write_json_atomic(config_path(), data)


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def event_path(project_id: str) -> Path:
    return water_home() / "projects" / project_id / "events.jsonl"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"corrupt JSONL at {path}:{line_number}") from exc
    return records


def append_event(event: dict[str, Any]) -> bool:
    path = event_path(event["project_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        for line in handle:
            if line.strip() and json.loads(line).get("event_id") == event["event_id"]:
                return False
        handle.seek(0, os.SEEK_END)
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return True


def has_session(project_id: str, session_id: str) -> bool:
    return any(record.get("session_id") == session_id for record in _read_jsonl(event_path(project_id)))


def iter_events(project_ids: Iterable[str] | None = None) -> Iterable[dict[str, Any]]:
    config = load_config()
    wanted = set(project_ids or [project["id"] for project in config["projects"] if project.get("enabled", True)])
    for project_id in sorted(wanted):
        yield from _read_jsonl(event_path(project_id))


def append_recommendation_record(record: dict[str, Any]) -> None:
    path = recommendations_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def recommendation_states() -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    for record in _read_jsonl(recommendations_path()):
        recommendation_id = record["id"]
        if record.get("record_type") == "recommendation":
            states[recommendation_id] = dict(record)
            states[recommendation_id]["validation_count"] = 0
        elif recommendation_id in states:
            states[recommendation_id]["status"] = record["status"]
            states[recommendation_id]["updated_at"] = record["timestamp"]
            states[recommendation_id].setdefault("history", []).append(record)
            if record["status"] == "verified":
                states[recommendation_id]["validation_count"] += 1
    return states


def rebuild_guidance() -> None:
    lines = ["# Accepted Water Guidance", "", "Generated from explicit human decisions. Project-specific guidance applies only to its project.", ""]
    for item in sorted(recommendation_states().values(), key=lambda value: value["id"]):
        status = item.get("status")
        is_global = item.get("scope", "global") == "global"
        promoted = status in {"accepted", "verified"} and (not is_global or item.get("validation_count", 0) >= 3)
        if promoted:
            lines.extend([
                f"## {item['id']}: {item.get('title', item.get('category', 'Guidance'))}",
                "",
                f"- Scope: {item.get('scope', 'global')}",
                f"- Guidance: {item.get('proposed_change', '')}",
                f"- Validation: {item.get('validation_metric', '')}",
                "",
            ])
    if len(lines) == 4:
        lines.append("No guidance has been approved yet.")
    guidance_path().parent.mkdir(parents=True, exist_ok=True)
    guidance_path().write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def prune_events(retention_days: int) -> tuple[int, int]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    kept_total = removed_total = 0
    for project_dir in (water_home() / "projects").glob("*"):
        path = project_dir / "events.jsonl"
        if not path.exists():
            continue
        kept = []
        for record in _read_jsonl(path):
            timestamp = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
            if timestamp >= cutoff:
                kept.append(record)
                kept_total += 1
            else:
                removed_total += 1
        temporary = path.with_suffix(".jsonl.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            for record in kept:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        os.replace(temporary, path)
    return kept_total, removed_total
