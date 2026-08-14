from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import watcher_home
from .store import atomic_json, read_jsonl
from .tasks import task_path


def generate_trend(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("confirmed"):
        raise ValueError("trend generation requires current user confirmation")
    records = read_jsonl(task_path(project_id))
    completed = {item["task_id"] for item in records if item.get("record_type") == "finished"
                 and item.get("status") == "completed" and item.get("outcome_met")}
    if len(completed) < 3:
        raise ValueError("at least three completed tasks are required")
    patterns = payload.get("patterns", [])
    if not isinstance(patterns, list):
        raise ValueError("patterns must be a list")
    for pattern in patterns:
        evidence = set(pattern.get("task_ids", []))
        if len(evidence) < 2 or not evidence <= completed:
            raise ValueError("each repeated pattern requires evidence from two completed tasks")
        for key in ("pattern", "diagnosis", "next_step"):
            if not isinstance(pattern.get(key), str) or not pattern[key]:
                raise ValueError(f"pattern {key} is required")
    generated = datetime.now(timezone.utc).isoformat()
    identifier = "trend-" + hashlib.sha256(f"{project_id}:{generated}".encode()).hexdigest()[:12]
    report = {"schema_version": 1, "id": identifier, "project_id": project_id, "status": "generated",
              "generated_at": generated, "completed_task_count": len(completed), "patterns": patterns,
              "dimension_trends": payload.get("dimension_trends", {}),
              "verified_improvements": payload.get("verified_improvements", []),
              "unknown": payload.get("unknown", [])}
    atomic_json(watcher_home() / "trends" / project_id / f"{identifier}.json", report)
    return report
