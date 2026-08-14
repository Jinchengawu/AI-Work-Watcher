from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from .paths import watcher_home
from .store import append_jsonl, read_jsonl


def proposal_path():
    return watcher_home() / "proposals.jsonl"


def create_proposal(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    required = ("target_asset", "specific_change", "evidence_ids", "expected_effect",
                "validation_metric", "rollback_condition")
    if any(not payload.get(key) for key in required):
        raise ValueError("proposal requires target, change, evidence, effect, metric, and rollback")
    now = datetime.now(timezone.utc).isoformat()
    identifier = "prop-" + hashlib.sha256(f"{project_id}:{now}:{payload['target_asset']}".encode()).hexdigest()[:12]
    record = {"schema_version": 1, "record_type": "proposal", "id": identifier,
              "project_id": project_id, "status": "proposed", "created_at": now, **payload}
    append_jsonl(proposal_path(), record)
    return record

def proposal_states() -> dict[str, dict[str, Any]]:
    states = {}
    for record in read_jsonl(proposal_path()):
        if record["record_type"] == "proposal":
            states[record["id"]] = dict(record)
        else:
            states[record["id"]].update({"status": record["status"], "updated_at": record["timestamp"]})
    return states


def transition_proposal(identifier: str, action: str, note: str = "", result: str | None = None) -> dict[str, Any]:
    states = proposal_states()
    if identifier not in states:
        raise ValueError(f"unknown proposal: {identifier}")
    current = states[identifier]["status"]
    allowed = {("proposed", "accept"): "accepted", ("proposed", "reject"): "rejected",
               ("accepted", "reject"): "rejected", ("accepted", "verify"): "verified" if result == "pass" else "retired",
               ("verified", "verify"): "verified" if result == "pass" else "retired"}
    if (current, action) not in allowed:
        raise ValueError(f"cannot {action} proposal in {current} state")
    record = {"schema_version": 1, "record_type": "transition", "id": identifier, "action": action,
              "status": allowed[(current, action)], "result": result, "note": note,
              "timestamp": datetime.now(timezone.utc).isoformat()}
    append_jsonl(proposal_path(), record)
    return record
