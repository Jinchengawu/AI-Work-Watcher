from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .assets import archive_asset, promote_asset
from .hooks import read_hook_payload, record_hook
from .install import doctor, install, uninstall
from .legacy_v0 import migrate_legacy_v0
from .paths import watcher_home
from .projects import add_project, remove_project, resolve_project
from .proposals import transition_proposal
from .store import load_config
from .structure import capture_snapshot
from .tasks import finish_task, prepare_task, prune_tasks
from .trends import generate_trend


def _stdin() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON on stdin: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("stdin must contain a JSON object")
    return value


def _project(args: argparse.Namespace) -> dict[str, Any]:
    result = resolve_project(getattr(args, "cwd", None), getattr(args, "project_id", None))
    if not result:
        raise ValueError("path is not an explicitly registered project")
    return result


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="ai-work-watcher", description="Personal AI workflow coach control plane")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("install").add_argument("--force", action="store_true")
    commands.add_parser("uninstall").add_argument("--purge-data", action="store_true")
    commands.add_parser("doctor")

    project = commands.add_parser("project").add_subparsers(dest="action", required=True)
    add = project.add_parser("add"); add.add_argument("path"); add.add_argument("--name"); add.add_argument("--id"); add.add_argument("--provider", choices=["auto", "codex", "claude"], default="auto")
    remove = project.add_parser("remove"); remove.add_argument("id")
    project.add_parser("list")
    inspect = project.add_parser("inspect"); inspect.add_argument("--project-id"); inspect.add_argument("--cwd")

    task = commands.add_parser("task").add_subparsers(dest="action", required=True)
    for action in ("prepare", "finish"):
        item = task.add_parser(action); item.add_argument("--stdin", action="store_true", required=True); item.add_argument("--project-id"); item.add_argument("--cwd")

    prompt = commands.add_parser("prompt").add_subparsers(dest="action", required=True)
    for action in ("list", "show"):
        item = prompt.add_parser(action); item.add_argument("slug", nargs="?"); item.add_argument("--project-id"); item.add_argument("--cwd")
    promote = prompt.add_parser("promote"); promote.add_argument("task_id"); promote.add_argument("slug"); promote.add_argument("--title", required=True); promote.add_argument("--kind", choices=["prompt", "workflow"], default="prompt"); promote.add_argument("--approved", action="store_true"); promote.add_argument("--project-id"); promote.add_argument("--cwd")
    archive = prompt.add_parser("archive"); archive.add_argument("slug"); archive.add_argument("--kind", choices=["prompt", "workflow"], default="prompt"); archive.add_argument("--approved", action="store_true"); archive.add_argument("--project-id"); archive.add_argument("--cwd")

    trends = commands.add_parser("trends").add_subparsers(dest="action", required=True)
    generate = trends.add_parser("generate"); generate.add_argument("--stdin", action="store_true", required=True); generate.add_argument("--project-id"); generate.add_argument("--cwd")
    proposal = commands.add_parser("proposal").add_subparsers(dest="action", required=True)
    for action in ("accept", "reject"):
        item = proposal.add_parser(action); item.add_argument("id"); item.add_argument("--note", default="")
    verify = proposal.add_parser("verify"); verify.add_argument("id"); verify.add_argument("--result", choices=["pass", "fail"], required=True); verify.add_argument("--note", default="")
    migrate = commands.add_parser("migrate").add_subparsers(dest="action", required=True); migrate.add_parser("legacy-v0")
    hook = commands.add_parser("hook"); hook.add_argument("source", choices=["codex", "claude"]); hook.add_argument("payload", nargs="?")
    commands.add_parser("prune")
    return root


def run(args: argparse.Namespace) -> int:
    if args.command == "install": print(json.dumps(install(args.force))); return 0
    if args.command == "uninstall": print(json.dumps(uninstall(args.purge_data))); return 0
    if args.command == "doctor":
        checks = doctor()
        for item in checks: print(f"{item['status'].upper():4}  {item['host']}: {item['label']}")
        host_ok = any(item["host"] in {"codex", "claude"} and item["status"] == "ok" for item in checks)
        return 0 if checks[0]["status"] == "ok" and host_ok else 1
    if args.command == "project":
        if args.action == "add": value = add_project(args.path, args.name, args.id, args.provider)
        elif args.action == "remove": value = remove_project(args.id)
        elif args.action == "list": value = load_config()["projects"]
        else: value = capture_snapshot(_project(args))
        print(json.dumps(value, ensure_ascii=False, indent=2)); return 0
    if args.command == "task":
        project = _project(args); value = prepare_task(project["id"], _stdin()) if args.action == "prepare" else finish_task(project["id"], _stdin())
        print(json.dumps(value, ensure_ascii=False, indent=2)); return 0
    if args.command == "prompt":
        project = _project(args); root = Path(project["path"]) / ".ai-work-watcher"
        if args.action == "promote": value = promote_asset(project, args.task_id, args.kind, args.slug, args.title, args.approved)
        elif args.action == "archive": value = {"archived": archive_asset(project, args.kind, args.slug, args.approved)}
        else:
            assets = []
            for index in root.glob("*/index.json"): assets.extend(json.loads(index.read_text(encoding="utf-8"))["assets"])
            if args.action == "show":
                matches = [item for item in assets if item["slug"] == args.slug]
                if not matches: raise ValueError(f"unknown asset: {args.slug}")
                value = matches
            else: value = assets
        print(json.dumps(value, ensure_ascii=False, indent=2)); return 0
    if args.command == "trends":
        project = _project(args); print(json.dumps(generate_trend(project["id"], _stdin()), ensure_ascii=False, indent=2)); return 0
    if args.command == "proposal":
        print(json.dumps(transition_proposal(args.id, args.action, args.note, getattr(args, "result", None)), ensure_ascii=False, indent=2)); return 0
    if args.command == "migrate": print(json.dumps(migrate_legacy_v0(), ensure_ascii=False, indent=2)); return 0
    if args.command == "hook":
        recorded, message = record_hook(args.source, read_hook_payload(args.payload)); print(json.dumps({"recorded": recorded, "message": message})); return 0
    if args.command == "prune":
        days = int(load_config().get("retention_days", 180)); kept, removed = prune_tasks(days)
        print(json.dumps({"retention_days": days, "kept": kept, "removed": removed})); return 0
    return 2


def main(argv: list[str] | None = None) -> int:
    try:
        return run(parser().parse_args(argv))
    except (ValueError, OSError) as exc:
        print(f"ai-work-watcher: {exc}", file=sys.stderr); return 1
