from __future__ import annotations

import json
import os
import sys
from typing import Any

from .projects import resolve_project
from .store import read_jsonl
from .tasks import finish_task, task_path


def read_hook_payload(argument: str | None = None) -> dict[str, Any]:
    raw = argument if argument is not None else (sys.stdin.read() if not sys.stdin.isatty() else "")
    try:
        value = json.loads(raw) if raw else {}
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def record_hook(source: str, payload: dict[str, Any]) -> tuple[bool, str]:
    if os.environ.get("AI_WORK_WATCHER_INTERNAL_RUN") == "1":
        return False, "internal run ignored"
    cwd = payload.get("cwd") or payload.get("project_dir") or payload.get("workspace") or os.getcwd()
    project = resolve_project(str(cwd))
    if not project:
        return False, "unregistered project ignored"
    raw_session = str(payload.get("session_id") or payload.get("thread_id") or payload.get("conversation_id") or "unknown")
    hashed = __import__("hashlib").sha256(raw_session.encode()).hexdigest()[:16]
    session_id = "session-" + hashed
    if any(item.get("session_id") == session_id and item.get("record_type") == "prepared"
           for item in read_jsonl(task_path(project["id"]))):
        prepared = next(item for item in reversed(read_jsonl(task_path(project["id"])))
                        if item.get("session_id") == session_id and item.get("record_type") == "prepared")
        if any(item.get("task_id") == prepared["task_id"] and item.get("record_type") == "finished"
               for item in read_jsonl(task_path(project["id"]))):
            return False, "structured Finish already recorded"
        result = finish_task(project["id"], {"task_id": prepared["task_id"], "status": "unknown",
            "outcome_met": False, "result_summary": "Session ended without a structured Finish."}, fallback=True)
    else:
        result = finish_task(project["id"], {"raw_session_id": raw_session, "status": "unknown",
            "outcome_met": False, "result_summary": f"{source} SessionEnd fallback."}, fallback=True)
    return bool(result["recorded"]), result["task_id"]
