from __future__ import annotations

import json
import os
import sys
from typing import Any

from .projects import resolve_project
from .schema import normalize_event
from .store import append_event, has_session


def read_hook_payload(argument: str | None = None) -> dict[str, Any]:
    raw = argument
    if raw is None and not sys.stdin.isatty():
        raw = sys.stdin.read()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def record_hook(source: str, payload: dict[str, Any]) -> tuple[bool, str]:
    if os.environ.get("WATER_INTERNAL_RUN") == "1":
        return False, "internal Water run ignored"
    cwd = payload.get("cwd") or payload.get("project_dir") or payload.get("workspace") or os.getcwd()
    project = resolve_project(str(cwd))
    if not project:
        return False, "unregistered project ignored"
    raw_session = str(payload.get("session_id") or payload.get("thread_id") or payload.get("conversation_id") or "unknown")
    probe = normalize_event({
        "source_terminal": source,
        "model": payload.get("model") or payload.get("model_name") or "unknown",
        "source_version": payload.get("version") or "unknown",
        "raw_session_id": raw_session,
        "event_type": "session_closed",
        "goal": "Session ended without a structured Water summary",
        "actions": [],
        "outcome": "Terminal lifecycle hook observed the session end",
        "status": "unknown",
        "evidence": [{"kind": "hook", "summary": f"{source} SessionEnd"}],
        "blockers": [],
        "risks": ["Structured session summary was not recorded"],
        "metrics": {},
        "tags": ["fallback", "session-end"],
        "confidence": 0.2,
    }, project["id"])
    if has_session(project["id"], probe["session_id"]):
        return False, "session already recorded"
    return append_event(probe), probe["event_id"]
