from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .paths import watcher_home
from .redact import redact
from .store import append_jsonl, read_jsonl, rewrite_jsonl

DIMENSIONS = ("task_definition", "context_structure", "prompt_effectiveness",
              "execution_verification", "result_adjusted_efficiency")
STATE_BY_SCORE = {1: "needs_attention", 2: "unstable", 3: "developing", 4: "healthy", 5: "repeatable", None: "unknown"}
FORBIDDEN = {"transcript", "full_response", "source_code", "diff", "patch", "terminal_output"}


def task_path(project_id: str) -> Path:
    return watcher_home() / "tasks" / f"{project_id}.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reject_forbidden(value: object, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in FORBIDDEN:
                raise ValueError(f"forbidden field at {path}.{key}")
            _reject_forbidden(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_forbidden(item, f"{path}[{index}]")


def _brief(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("task_brief must be an object")
    required = {"goal", "context", "constraints", "acceptance_criteria", "unknowns",
                "recommended_workflow", "refined_prompt"}
    missing = required - set(value)
    if missing:
        raise ValueError("task_brief missing: " + ", ".join(sorted(missing)))
    if set(value) - required:
        raise ValueError("task_brief contains unknown fields")
    for key in ("context", "constraints", "acceptance_criteria", "unknowns", "recommended_workflow"):
        if not isinstance(value[key], list):
            raise ValueError(f"task_brief.{key} must be a list")
    return value


def prepare_task(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _reject_forbidden(payload)
    brief = _brief(payload.get("task_brief"))
    if not payload.get("approved"):
        gaps = []
        if not brief["acceptance_criteria"]:
            gaps.append("acceptance_criteria")
        return {"recorded": False, "approval_required": True, "gaps": gaps, "task_brief": brief}
    for key in ("source", "raw_session_id", "original_prompt"):
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            raise ValueError(f"{key} is required")
    seed = f"{project_id}:{payload['raw_session_id']}"
    task_id = "task-" + hashlib.sha256(seed.encode()).hexdigest()[:16]
    record = redact({"schema_version": 1, "record_type": "prepared", "task_id": task_id,
                     "project_id": project_id, "source": payload["source"],
                     "session_id": "session-" + hashlib.sha256(payload["raw_session_id"].encode()).hexdigest()[:16],
                     "original_prompt": payload["original_prompt"], "task_brief": brief, "timestamp": _now()})
    inserted = append_jsonl(task_path(project_id), record, "task_id")
    if inserted:
        from .projects import resolve_project
        from .structure import capture_snapshot
        project = resolve_project(project_id=project_id)
        if project: capture_snapshot(project)
    return {"recorded": inserted, "task_id": task_id, "status": "prepared"}


def _validate_dimensions(value: object, outcome_met: bool) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(DIMENSIONS):
        raise ValueError("dimensions must contain exactly the five supported dimensions")
    for name, item in value.items():
        if not isinstance(item, dict):
            raise ValueError(f"dimension {name} must be an object")
        score = item.get("score")
        required = {"score", "state", "confidence", "evidence_ids", "diagnosis", "next_step"}
        if set(item) != required:
            raise ValueError(f"dimension {name} contains unknown or missing fields")
        if (score is not None and type(score) is not int) or score not in STATE_BY_SCORE or item.get("state") != STATE_BY_SCORE[score]:
            raise ValueError(f"dimension {name} has an invalid score/state mapping")
        if type(item.get("confidence")) not in {int, float} or not 0 <= item["confidence"] <= 1:
            raise ValueError(f"dimension {name} confidence must be between 0 and 1")
        if not isinstance(item.get("evidence_ids"), list) or not all(isinstance(x, str) for x in item["evidence_ids"]):
            raise ValueError(f"dimension {name} evidence_ids must be a list")
        for key in ("diagnosis", "next_step"):
            if not isinstance(item.get(key), str) or not item[key]:
                raise ValueError(f"dimension {name} {key} is required")
    efficiency = value["result_adjusted_efficiency"]
    if not outcome_met and efficiency["score"] is not None:
        raise ValueError("result-adjusted efficiency must be unknown when the outcome was not met")
    return value


def finish_task(project_id: str, payload: dict[str, Any], fallback: bool = False) -> dict[str, Any]:
    _reject_forbidden(payload)
    task_id = payload.get("task_id")
    records = read_jsonl(task_path(project_id))
    if task_id and not any(item.get("task_id") == task_id and item.get("record_type") == "prepared" for item in records):
        raise ValueError(f"unknown prepared task: {task_id}")
    if not task_id and not fallback:
        raise ValueError("task_id is required")
    if fallback and not task_id:
        session_id = payload.get("raw_session_id", "unknown")
        task_id = "fallback-" + hashlib.sha256(f"{project_id}:{session_id}".encode()).hexdigest()[:16]
        if any(item.get("task_id") == task_id for item in records):
            return {"recorded": False, "task_id": task_id, "status": "unknown"}
    if any(item.get("task_id") == task_id and item.get("record_type") == "finished" for item in records):
        return {"recorded": False, "task_id": task_id, "status": "duplicate"}
    status = payload.get("status", "unknown" if fallback else None)
    if status not in {"completed", "partial", "failed", "abandoned", "unknown"}:
        raise ValueError("invalid finish status")
    outcome_met = bool(payload.get("outcome_met", False))
    result_summary = payload.get("result_summary", "Session ended without a structured Finish.")
    if not isinstance(result_summary, str) or len(result_summary) > 2000:
        raise ValueError("result_summary must be a string of at most 2000 characters")
    dimensions = payload.get("dimensions")
    if fallback:
        dimensions = {name: {"score": None, "state": "unknown", "confidence": 0.1,
                             "evidence_ids": [], "diagnosis": "Structured Finish was not recorded.",
                             "next_step": "Use the Skill Finish flow for the next task."} for name in DIMENSIONS}
    dimensions = _validate_dimensions(dimensions, outcome_met)
    verification = payload.get("verification", [])
    if not isinstance(verification, list) or not all(isinstance(item, dict) for item in verification):
        raise ValueError("verification must be a list of evidence objects")
    for index, item in enumerate(verification):
        item.setdefault("id", f"ev-{task_id}-{index + 1}")
        if set(item) != {"id", "kind", "summary"}:
            raise ValueError("verification evidence permits only id, kind, and summary")
        if not isinstance(item.get("kind"), str) or not isinstance(item.get("summary"), str):
            raise ValueError("verification evidence requires kind and summary")
        if len(item["summary"]) > 500:
            raise ValueError("verification summary is too long")
    rework = payload.get("rework_reasons", [])
    if not isinstance(rework, list) or not all(isinstance(item, str) and len(item) <= 500 for item in rework):
        raise ValueError("rework_reasons must be short strings")
    metrics = payload.get("metrics", {})
    allowed_metrics = {"elapsed_seconds", "turns", "tool_calls", "tokens", "cost"}
    if not isinstance(metrics, dict) or set(metrics) - allowed_metrics:
        raise ValueError("metrics contains unsupported fields")
    if any(type(value) not in {int, float} or value < 0 for value in metrics.values()):
        raise ValueError("metrics values must be non-negative numbers")
    evidence_ids = {item["id"] for item in verification}
    referenced = {evidence for item in dimensions.values() for evidence in item["evidence_ids"]}
    if referenced - evidence_ids:
        raise ValueError("dimension evidence_ids must reference Finish verification evidence")
    record = redact({"schema_version": 1, "record_type": "finished", "task_id": task_id,
                     "project_id": project_id, "status": status, "outcome_met": outcome_met,
                     "result_summary": result_summary, "verification": verification, "rework_reasons": rework,
                     "metrics": metrics, "dimensions": dimensions,
                     "confidence": 0.1 if fallback else payload.get("confidence", 0.8),
                     "timestamp": _now()})
    append_jsonl(task_path(project_id), record)
    for dimension, observation in dimensions.items():
        append_jsonl(watcher_home() / "observations" / f"{project_id}.jsonl",
                     {"schema_version": 1, "task_id": task_id, "project_id": project_id,
                      "dimension": dimension, "timestamp": record["timestamp"], **observation})
    from .projects import resolve_project
    from .structure import capture_snapshot
    project = resolve_project(project_id=project_id)
    if project: capture_snapshot(project)
    completed = sum(item.get("record_type") == "finished" and item.get("status") == "completed"
                    and item.get("outcome_met") for item in read_jsonl(task_path(project_id)))
    return {"recorded": True, "task_id": task_id, "status": status,
            "trend_ready": completed >= 3, "completed_task_count": completed}


def prune_tasks(retention_days: int) -> tuple[int, int]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    kept_total = removed_total = 0
    directory = watcher_home() / "tasks"
    if not directory.exists(): return 0, 0
    for path in directory.glob("*.jsonl"):
        records = read_jsonl(path)
        latest = {}
        for record in records:
            stamp = datetime.fromisoformat(record["timestamp"])
            latest[record["task_id"]] = max(latest.get(record["task_id"], stamp), stamp)
        kept = [record for record in records if latest[record["task_id"]] >= cutoff]
        kept_total += len(kept); removed_total += len(records) - len(kept)
        rewrite_jsonl(path, kept)
    return kept_total, removed_total
