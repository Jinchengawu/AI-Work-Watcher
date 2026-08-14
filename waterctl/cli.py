from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .hooks import read_hook_payload, record_hook
from .install import doctor, install, uninstall
from .paths import water_home
from .projects import add_project, remove_project, resolve_project
from .review import ReviewError, run_weekly
from .schema import ValidationError, normalize_event
from .store import (
    append_event, append_recommendation_record, ensure_home, load_config,
    prune_events, rebuild_guidance, recommendation_states,
)


def _read_stdin_json() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON on stdin: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("stdin must contain a JSON object")
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="waterctl", description="Water Supervisor control plane")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    project = commands.add_parser("project", help="manage explicitly registered projects")
    project_commands = project.add_subparsers(dest="project_command", required=True)
    project_add = project_commands.add_parser("add")
    project_add.add_argument("path")
    project_add.add_argument("--name")
    project_add.add_argument("--id")
    project_add.add_argument("--sensitivity", choices=["standard", "sensitive"], default="standard")
    project_add.add_argument("--provider", choices=["auto", "codex", "claude"], default="auto")
    project_remove = project_commands.add_parser("remove")
    project_remove.add_argument("id")
    project_commands.add_parser("list")

    record = commands.add_parser("record", help="record a structured, redacted session event")
    record.add_argument("--stdin", action="store_true", required=True)
    record.add_argument("--project-id")
    record.add_argument("--cwd")

    hook = commands.add_parser("hook", help="consume a terminal lifecycle event")
    hook.add_argument("source", choices=["codex", "claude"])
    hook.add_argument("payload", nargs="?")

    review = commands.add_parser("review", help="generate evidence-backed reviews")
    review_commands = review.add_subparsers(dest="review_command", required=True)
    weekly = review_commands.add_parser("weekly")
    weekly.add_argument("--provider", choices=["auto", "codex", "claude"], default="auto")
    weekly.add_argument("--week")

    recommend = commands.add_parser("recommend", help="manage recommendation lifecycle")
    recommend_commands = recommend.add_subparsers(dest="recommend_command", required=True)
    for action in ("accept", "reject"):
        action_parser = recommend_commands.add_parser(action)
        action_parser.add_argument("id")
        action_parser.add_argument("--note", default="")
    verify = recommend_commands.add_parser("verify")
    verify.add_argument("id")
    verify.add_argument("--result", choices=["pass", "fail"], required=True)
    verify.add_argument("--note", default="")

    install_parser = commands.add_parser("install", help="install skills, hooks, bootstrap, and schedule")
    install_parser.add_argument("--force", action="store_true")
    install_parser.add_argument("--no-schedule", action="store_true")
    uninstall_parser = commands.add_parser("uninstall", help="remove Water-managed integration files")
    uninstall_parser.add_argument("--purge-data", action="store_true")
    commands.add_parser("doctor", help="diagnose installation state")
    prune = commands.add_parser("prune", help="enforce event retention")
    prune.add_argument("--purge-data", action="store_true")
    return parser


def _transition_recommendation(identifier: str, action: str, note: str, result: str | None = None) -> dict[str, Any]:
    states = recommendation_states()
    if identifier not in states:
        raise ValueError(f"unknown recommendation: {identifier}")
    current = states[identifier].get("status")
    if action == "accept":
        if current != "proposed":
            raise ValueError(f"cannot accept recommendation in {current} state")
        status = "accepted"
    elif action == "reject":
        if current not in {"proposed", "accepted"}:
            raise ValueError(f"cannot reject recommendation in {current} state")
        status = "rejected"
    else:
        if current not in {"accepted", "verified"}:
            raise ValueError(f"cannot verify recommendation in {current} state")
        status = "verified" if result == "pass" else "retired"
    record = {
        "schema_version": 1,
        "record_type": "transition",
        "id": identifier,
        "action": action,
        "status": status,
        "result": result,
        "note": note,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    append_recommendation_record(record)
    rebuild_guidance()
    return record


def _run(args: argparse.Namespace) -> int:
    if args.command == "project":
        if args.project_command == "add":
            print(json.dumps(add_project(args.path, args.name, args.id, args.sensitivity, args.provider), ensure_ascii=False, indent=2))
        elif args.project_command == "remove":
            print(json.dumps(remove_project(args.id), ensure_ascii=False, indent=2))
        else:
            print(json.dumps(load_config()["projects"], ensure_ascii=False, indent=2))
        return 0

    if args.command == "record":
        raw = _read_stdin_json()
        project = resolve_project(args.cwd, args.project_id)
        if not project:
            raise ValueError("current path is not an explicitly registered project")
        event = normalize_event(raw, project["id"])
        inserted = append_event(event)
        print(json.dumps({"recorded": inserted, "event_id": event["event_id"]}))
        return 0

    if args.command == "hook":
        inserted, message = record_hook(args.source, read_hook_payload(args.payload))
        print(json.dumps({"recorded": inserted, "message": message}))
        return 0

    if args.command == "review":
        path = run_weekly(args.provider, args.week)
        print(path)
        return 0

    if args.command == "recommend":
        result = getattr(args, "result", None)
        print(json.dumps(_transition_recommendation(args.id, args.recommend_command, args.note, result), ensure_ascii=False, indent=2))
        return 0

    if args.command == "install":
        for path in install(args.force, not args.no_schedule):
            print(f"installed: {path}")
        return 0

    if args.command == "uninstall":
        for path in uninstall(args.purge_data):
            print(f"removed: {path}")
        return 0

    if args.command == "doctor":
        checks = doctor()
        for passed, label in checks:
            print(f"{'OK' if passed else 'FAIL'}  {label}")
        return 0 if all(passed for passed, _ in checks) else 1

    if args.command == "prune":
        if args.purge_data:
            if water_home().exists():
                shutil.rmtree(water_home())
            ensure_home()
            print("purged all Water data")
            return 0
        config = load_config()
        kept, removed = prune_events(int(config.get("retention_days", 180)))
        print(json.dumps({"kept": kept, "removed": removed}))
        return 0
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        return _run(parser.parse_args(argv))
    except (ValueError, ValidationError, ReviewError, OSError) as exc:
        print(f"waterctl: {exc}", file=sys.stderr)
        return 1
