from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .redact import redact


EVENT_FIELDS = {
    "schema_version", "event_id", "timestamp", "project_id", "source_terminal",
    "model", "source_version", "session_id", "event_type", "goal", "actions",
    "outcome", "status", "evidence", "blockers", "risks", "metrics", "tags",
    "confidence", "redaction_summary",
}
EVENT_STATUSES = {"completed", "partial", "blocked", "failed", "abandoned", "unknown"}
EVENT_TYPES = {"session_summary", "session_closed"}


class ValidationError(ValueError):
    pass


def _stable_hash(value: str, prefix: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}-{digest}"


def _require_text(data: dict[str, Any], key: str, limit: int, *, allow_empty: bool = False) -> None:
    value = data.get(key)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValidationError(f"{key} must be a non-empty string")
    if len(value) > limit:
        raise ValidationError(f"{key} exceeds {limit} characters")


def _require_list(data: dict[str, Any], key: str, *, limit: int = 20, evidence: bool = False) -> None:
    value = data.get(key)
    if not isinstance(value, list):
        raise ValidationError(f"{key} must be a list")
    if len(value) > limit:
        raise ValidationError(f"{key} exceeds {limit} items")
    for item in value:
        if isinstance(item, str):
            if len(item) > 500:
                raise ValidationError(f"{key} contains an item longer than 500 characters")
            continue
        if not evidence or not isinstance(item, dict):
            raise ValidationError(f"{key} items must be strings")
        if set(item) - {"kind", "ref", "summary"}:
            raise ValidationError("evidence objects may contain only kind, ref, and summary")
        if not item or any(not isinstance(value, str) or len(value) > 500 for value in item.values()):
            raise ValidationError("evidence object values must be strings up to 500 characters")


def normalize_event(raw: dict[str, Any], project_id: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValidationError("event must be a JSON object")
    unknown = set(raw) - EVENT_FIELDS - {"raw_session_id"}
    if unknown:
        raise ValidationError(f"unknown event fields: {', '.join(sorted(unknown))}")

    source_session = str(raw.get("raw_session_id") or raw.get("session_id") or "unknown")
    base = dict(raw)
    base.pop("raw_session_id", None)
    base["schema_version"] = base.get("schema_version", 1)
    base["timestamp"] = base.get("timestamp") or datetime.now(timezone.utc).isoformat()
    base["project_id"] = project_id
    base["source_terminal"] = base.get("source_terminal", "unknown")
    base["model"] = base.get("model", "unknown")
    base["source_version"] = base.get("source_version", "unknown")
    base["session_id"] = _stable_hash(source_session, "session")
    base["event_type"] = base.get("event_type", "session_summary")
    base["goal"] = base.get("goal", "Unknown session goal")
    base["actions"] = base.get("actions", [])
    base["outcome"] = base.get("outcome", "No structured outcome was recorded")
    base["status"] = base.get("status", "unknown")
    base["evidence"] = base.get("evidence", [])
    base["blockers"] = base.get("blockers", [])
    base["risks"] = base.get("risks", [])
    base["metrics"] = base.get("metrics", {})
    base["tags"] = base.get("tags", [])
    base["confidence"] = base.get("confidence", 0.5)
    base.pop("redaction_summary", None)

    sanitized, redaction_summary = redact(base)
    sanitized["redaction_summary"] = redaction_summary
    identity = json.dumps(sanitized, sort_keys=True, ensure_ascii=False)
    sanitized["event_id"] = sanitized.get("event_id") or _stable_hash(identity, "evt")
    validate_event(sanitized)
    return sanitized


def validate_event(data: dict[str, Any]) -> None:
    if set(data) != EVENT_FIELDS:
        missing = EVENT_FIELDS - set(data)
        extra = set(data) - EVENT_FIELDS
        raise ValidationError(f"event fields mismatch; missing={sorted(missing)}, extra={sorted(extra)}")
    if data["schema_version"] != 1:
        raise ValidationError("schema_version must be 1")
    for key, limit in (
        ("event_id", 80), ("timestamp", 80), ("project_id", 80),
        ("source_terminal", 40), ("model", 100), ("source_version", 100),
        ("session_id", 80), ("event_type", 40), ("goal", 2000),
        ("outcome", 2000), ("status", 40),
    ):
        _require_text(data, key, limit)
    try:
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError("timestamp must be ISO-8601") from exc
    if data["status"] not in EVENT_STATUSES:
        raise ValidationError(f"invalid status: {data['status']}")
    if data["event_type"] not in EVENT_TYPES:
        raise ValidationError(f"invalid event_type: {data['event_type']}")
    for key in ("actions", "blockers", "risks", "tags"):
        _require_list(data, key)
    _require_list(data, "evidence", evidence=True)
    if not isinstance(data["metrics"], dict):
        raise ValidationError("metrics must be an object")
    if len(data["metrics"]) > 30:
        raise ValidationError("metrics exceeds 30 fields")
    for key, value in data["metrics"].items():
        if not isinstance(key, str) or len(key) > 80:
            raise ValidationError("metric names must be strings up to 80 characters")
        if value is not None and not isinstance(value, (int, float, bool)):
            raise ValidationError("metric values must be numeric, boolean, or null")
    if not isinstance(data["redaction_summary"], dict):
        raise ValidationError("redaction_summary must be an object")
    if not isinstance(data["confidence"], (int, float)) or not 0 <= data["confidence"] <= 1:
        raise ValidationError("confidence must be between 0 and 1")
