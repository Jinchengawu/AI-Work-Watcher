from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .store import atomic_json, read_jsonl
from .tasks import task_path


def _safe_slug(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
        raise ValueError("slug must use lowercase letters, numbers, and hyphens")
    return value


def promote_asset(project: dict[str, Any], task_id: str, kind: str, slug: str, title: str,
                  approved: bool = False) -> dict[str, Any]:
    if not approved:
        raise ValueError("explicit approval is required")
    if kind not in {"prompt", "workflow"}:
        raise ValueError("kind must be prompt or workflow")
    records = [item for item in read_jsonl(task_path(project["id"])) if item.get("task_id") == task_id]
    prepared = next((item for item in records if item.get("record_type") == "prepared"), None)
    finished = next((item for item in records if item.get("record_type") == "finished"), None)
    if not prepared or not finished or finished.get("status") != "completed" or not finished.get("outcome_met"):
        raise ValueError("only a successfully completed task can be promoted")
    slug = _safe_slug(slug)
    folder = "prompts" if kind == "prompt" else "workflows"
    directory = Path(project["path"]) / ".ai-work-watcher" / folder
    index_path = directory / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"schema_version": 1, "assets": []}
    revisions = [int(item["revision"]) for item in index["assets"] if item["slug"] == slug]
    revision = max(revisions, default=0) + 1
    path = directory / f"{slug}-r{revision}.md"
    directory.mkdir(parents=True, exist_ok=True)
    if kind == "prompt":
        body = prepared["task_brief"]["refined_prompt"]
    else:
        body = "\n".join(f"{index}. {step}" for index, step in enumerate(prepared["task_brief"]["recommended_workflow"], 1))
    path.write_text(f"# {title}\n\nRevision: {revision}\nSource task: {task_id}\n\n{body}\n", encoding="utf-8")
    entry = {"slug": slug, "title": title, "kind": kind, "revision": revision,
             "path": path.relative_to(Path(project["path"])).as_posix(), "source_task_id": task_id,
             "status": "active", "promoted_at": datetime.now(timezone.utc).isoformat()}
    index["assets"].append(entry)
    atomic_json(index_path, index)
    return entry


def archive_asset(project: dict[str, Any], kind: str, slug: str, approved: bool = False) -> int:
    if not approved:
        raise ValueError("explicit approval is required")
    folder = "prompts" if kind == "prompt" else "workflows"
    index_path = Path(project["path"]) / ".ai-work-watcher" / folder / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    changed = 0
    for item in index["assets"]:
        if item["slug"] == slug and item["status"] == "active":
            item["status"] = "archived"
            changed += 1
    atomic_json(index_path, index)
    return changed
