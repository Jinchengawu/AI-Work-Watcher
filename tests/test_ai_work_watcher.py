from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_work_watcher.projects import add_project, resolve_project
from ai_work_watcher.tasks import finish_task, prepare_task, prune_tasks
from ai_work_watcher.structure import capture_snapshot
from ai_work_watcher.assets import promote_asset
from ai_work_watcher.trends import generate_trend
from ai_work_watcher.proposals import create_proposal, transition_proposal
from ai_work_watcher.hooks import record_hook
from ai_work_watcher.install import MARKER_START, doctor, install, uninstall
from ai_work_watcher.legacy_v0 import migrate_legacy_v0


class WorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="ai-work-watcher-")
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.data = self.root / "data"
        self.project = self.root / "project"
        self.home.mkdir()
        self.project.mkdir()
        self.env = patch.dict(os.environ, {
            "HOME": str(self.home),
            "AI_WORK_WATCHER_HOME": str(self.data),
        })
        self.env.start()
        self.registration = add_project(str(self.project), name="demo")

    def tearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()

    def brief(self) -> dict:
        return {
            "goal": "Add deterministic export",
            "context": ["Python CLI", "tests are under tests/"],
            "constraints": ["Do not change the public file format"],
            "acceptance_criteria": ["Focused tests pass"],
            "unknowns": [],
            "recommended_workflow": ["inspect", "test", "implement", "verify"],
            "refined_prompt": "Add deterministic export and prove it with focused tests.",
        }

    def test_prepare_requires_approval_and_never_writes_project_assets(self) -> None:
        before = sorted(path.relative_to(self.project) for path in self.project.rglob("*"))
        preview = prepare_task(self.registration["id"], {
            "source": "codex", "raw_session_id": "s-1",
            "original_prompt": "add export", "task_brief": self.brief(), "approved": False,
        })
        self.assertFalse(preview["recorded"])
        self.assertEqual(before, sorted(path.relative_to(self.project) for path in self.project.rglob("*")))
        self.assertFalse((self.data / "tasks" / f"{self.registration['id']}.jsonl").exists())

    def test_finish_records_structured_evidence_without_forbidden_payloads(self) -> None:
        prepared = prepare_task(self.registration["id"], {
            "source": "claude", "raw_session_id": "s-2",
            "original_prompt": "add export", "task_brief": self.brief(), "approved": True,
        })
        result = finish_task(self.registration["id"], {
            "task_id": prepared["task_id"], "status": "completed", "outcome_met": True,
            "result_summary": "Export is deterministic.",
            "verification": [{"id": "ev-test", "kind": "test", "summary": "12 focused tests passed"}],
            "rework_reasons": [], "metrics": {"turns": 2, "tool_calls": 7, "tokens": 1800},
            "dimensions": {
                name: {"score": 4, "state": "healthy", "confidence": 0.8,
                       "evidence_ids": ["ev-test"], "diagnosis": "Clear and verified.",
                       "next_step": "Repeat on a comparable task."}
                for name in ("task_definition", "context_structure", "prompt_effectiveness",
                             "execution_verification", "result_adjusted_efficiency")
            },
        })
        stored = (self.data / "tasks" / f"{self.registration['id']}.jsonl").read_text()
        self.assertEqual(result["status"], "completed")
        for forbidden in ("transcript", "terminal_output", "diff", "source_code", "full_response"):
            self.assertNotIn(forbidden, stored)

    def _complete(self, session: str, score: int = 4) -> str:
        prepared = prepare_task(self.registration["id"], {
            "source": "codex", "raw_session_id": session, "original_prompt": "add export",
            "task_brief": self.brief(), "approved": True,
        })
        finish_task(self.registration["id"], {
            "task_id": prepared["task_id"], "status": "completed", "outcome_met": True,
            "result_summary": "done", "verification": [{"id": f"ev-{session}", "kind": "test", "summary": "passed"}],
            "rework_reasons": [], "metrics": {"turns": 2},
            "dimensions": {name: {"score": score, "state": "healthy" if score == 4 else "developing",
                "confidence": 0.8, "evidence_ids": [f"ev-{session}"], "diagnosis": "supported",
                "next_step": "repeat"} for name in ("task_definition", "context_structure",
                "prompt_effectiveness", "execution_verification", "result_adjusted_efficiency")},
        })
        return prepared["task_id"]

    def test_snapshot_detects_context_drift_and_ignores_secrets_and_dependencies(self) -> None:
        (self.project / "README.md").write_text("one\n")
        (self.project / ".env").write_text("SECRET=x\n")
        (self.project / "node_modules").mkdir()
        (self.project / "node_modules" / "x.js").write_text("generated")
        first = capture_snapshot(self.registration)
        (self.project / "README.md").write_text("two\n")
        (self.project / "AGENTS.md").write_text("instructions\n")
        second = capture_snapshot(self.registration)
        paths = json.dumps(second)
        self.assertNotIn(".env", paths)
        self.assertNotIn("node_modules", paths)
        self.assertIn("README.md", second["drift"]["changed"])
        self.assertIn("AGENTS.md", second["drift"]["added"])

    def test_successful_prompt_promotes_with_revisions_but_failed_task_cannot(self) -> None:
        task_id = self._complete("promote")
        first = promote_asset(self.registration, task_id, "prompt", "export", "Export", approved=True)
        second = promote_asset(self.registration, task_id, "prompt", "export", "Export", approved=True)
        self.assertEqual((first["revision"], second["revision"]), (1, 2))
        self.assertTrue((self.project / ".ai-work-watcher" / "prompts" / "export-r2.md").exists())
        self.assertTrue((self.project / ".ai-work-watcher" / "prompts" / "index.json").exists())

    def test_trends_require_three_completed_tasks_confirmation_and_cross_task_evidence(self) -> None:
        ids = [self._complete(f"trend-{index}") for index in range(3)]
        with self.assertRaises(ValueError):
            generate_trend(self.registration["id"], {"confirmed": False, "patterns": []})
        with self.assertRaises(ValueError):
            generate_trend(self.registration["id"], {"confirmed": True, "patterns": [{
                "pattern": "rework", "task_ids": [ids[0]], "diagnosis": "repeat issue", "next_step": "clarify"
            }]})
        report = generate_trend(self.registration["id"], {"confirmed": True, "patterns": [{
            "pattern": "verification helps", "task_ids": ids[:2], "diagnosis": "tests reduce rework",
            "next_step": "keep focused verification"
        }]})
        self.assertEqual(report["status"], "generated")
        self.assertNotIn("overall_score", report)

    def test_proposal_state_machine_tracks_validation_and_rollback(self) -> None:
        proposal = create_proposal(self.registration["id"], {
            "target_asset": ".ai-work-watcher/workflows/check.md", "specific_change": "add focused check",
            "evidence_ids": ["ev-1", "ev-2"], "expected_effect": "less rework",
            "validation_metric": "two comparable tasks pass", "rollback_condition": "cycle time rises",
        })
        accepted = transition_proposal(proposal["id"], "accept", "approved")
        verified = transition_proposal(proposal["id"], "verify", "worked", result="pass")
        self.assertEqual((accepted["status"], verified["status"]), ("accepted", "verified"))

    def test_session_end_is_low_confidence_fallback_and_deduplicates(self) -> None:
        first = record_hook("codex", {"cwd": str(self.project), "session_id": "hook-1"})
        second = record_hook("codex", {"cwd": str(self.project), "session_id": "hook-1"})
        self.assertTrue(first[0])
        self.assertFalse(second[0])
        stored = [json.loads(line) for line in (self.data / "tasks" / f"{self.registration['id']}.jsonl").read_text().splitlines()]
        self.assertEqual(stored[-1]["confidence"], 0.1)
        self.assertTrue(all(item["score"] is None for item in stored[-1]["dimensions"].values()))

    def test_install_is_idempotent_preserves_host_settings_and_has_no_scheduler(self) -> None:
        settings = self.home / ".claude/settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text('{"theme":"dark"}\n')
        with patch("ai_work_watcher.install.shutil.which", side_effect=lambda cmd: f"/usr/bin/{cmd}" if cmd == "codex" else None):
            install(); install()
            checks = doctor()
        self.assertEqual(json.loads(settings.read_text())["theme"], "dark")
        self.assertIn(MARKER_START, (self.home / ".codex/AGENTS.md").read_text())
        self.assertEqual(next(item for item in checks if item["host"] == "claude")["status"], "skip")
        self.assertFalse((self.home / "Library/LaunchAgents/com.ai-work-watcher.weekly.plist").exists())
        uninstall()
        self.assertEqual(json.loads(settings.read_text())["theme"], "dark")

    def test_legacy_migration_archives_without_importing_old_events_and_is_repeatable(self) -> None:
        legacy = self.root / "legacy"
        legacy.mkdir()
        (legacy / "events").mkdir()
        (legacy / "events/old.jsonl").write_text('{"score":6}\n')
        (legacy / "config.json").write_text(json.dumps({"projects": [{"id": "legacy-project",
            "name": "legacy", "path": str(self.project), "provider": "claude"}]}))
        with patch.dict(os.environ, {"AI_WORK_WATCHER_LEGACY_HOME": str(legacy)}):
            first = migrate_legacy_v0(); second = migrate_legacy_v0()
        self.assertEqual(first["status"], "migrated")
        self.assertEqual(second["status"], "already_migrated")
        self.assertTrue((self.data / "archive/legacy-v0/events/old.jsonl").exists())
        self.assertFalse((self.data / "tasks/legacy-project.jsonl").exists())

    def test_prepare_reports_missing_acceptance_criteria(self) -> None:
        brief = self.brief(); brief["acceptance_criteria"] = []
        result = prepare_task(self.registration["id"], {"source": "codex", "raw_session_id": "gap",
            "original_prompt": "do it", "task_brief": brief, "approved": False})
        self.assertEqual(result["gaps"], ["acceptance_criteria"])

    def test_prompts_are_redacted_before_private_storage(self) -> None:
        brief = self.brief(); brief["refined_prompt"] = "Use token=ghp_abcdefghijklmnopqrstuvwxyz1234"
        prepare_task(self.registration["id"], {"source": "codex", "raw_session_id": "redact",
            "original_prompt": "email dev@example.com", "task_brief": brief, "approved": True})
        stored = (self.data / "tasks" / f"{self.registration['id']}.jsonl").read_text()
        self.assertNotIn("dev@example.com", stored)
        self.assertNotIn("ghp_", stored)

    def test_finish_rejects_nested_forbidden_content_fields(self) -> None:
        task_id = prepare_task(self.registration["id"], {"source": "codex", "raw_session_id": "forbid",
            "original_prompt": "do it", "task_brief": self.brief(), "approved": True})["task_id"]
        with self.assertRaises(ValueError):
            finish_task(self.registration["id"], {"task_id": task_id, "status": "completed",
                "outcome_met": True, "verification": [{"terminal_output": "secret"}], "dimensions": {}})

    def test_finish_rejects_text_metrics_and_unstructured_evidence(self) -> None:
        task_id = prepare_task(self.registration["id"], {"source": "codex", "raw_session_id": "strict",
            "original_prompt": "do it", "task_brief": self.brief(), "approved": True})["task_id"]
        dimensions = {name: {"score": 4, "state": "healthy", "confidence": 0.8,
            "evidence_ids": ["ev-strict"], "diagnosis": "good", "next_step": "repeat"}
            for name in ("task_definition", "context_structure", "prompt_effectiveness",
                         "execution_verification", "result_adjusted_efficiency")}
        with self.assertRaisesRegex(ValueError, "metrics"):
            finish_task(self.registration["id"], {"task_id": task_id, "status": "completed", "outcome_met": True,
                "verification": [{"id": "ev-strict", "kind": "test", "summary": "passed"}],
                "metrics": {"notes": "raw output"}, "dimensions": dimensions})

    def test_failed_outcome_cannot_receive_efficiency_score(self) -> None:
        task_id = prepare_task(self.registration["id"], {"source": "codex", "raw_session_id": "failed",
            "original_prompt": "do it", "task_brief": self.brief(), "approved": True})["task_id"]
        dimensions = {name: {"score": 2, "state": "unstable", "confidence": 0.8,
            "evidence_ids": ["ev-fail"], "diagnosis": "failed", "next_step": "retry"}
            for name in ("task_definition", "context_structure", "prompt_effectiveness",
                         "execution_verification", "result_adjusted_efficiency")}
        with self.assertRaisesRegex(ValueError, "efficiency"):
            finish_task(self.registration["id"], {"task_id": task_id, "status": "failed", "outcome_met": False,
                "verification": [{"id": "ev-fail", "kind": "test", "summary": "failed"}], "dimensions": dimensions})

    def test_dimension_cannot_reference_unknown_evidence(self) -> None:
        task_id = prepare_task(self.registration["id"], {"source": "codex", "raw_session_id": "evidence",
            "original_prompt": "do it", "task_brief": self.brief(), "approved": True})["task_id"]
        dimensions = {name: {"score": 4, "state": "healthy", "confidence": 0.8,
            "evidence_ids": ["ev-missing"], "diagnosis": "good", "next_step": "repeat"}
            for name in ("task_definition", "context_structure", "prompt_effectiveness",
                         "execution_verification", "result_adjusted_efficiency")}
        with self.assertRaisesRegex(ValueError, "evidence_ids"):
            finish_task(self.registration["id"], {"task_id": task_id, "status": "completed", "outcome_met": True,
                "verification": [{"id": "ev-real", "kind": "test", "summary": "passed"}], "dimensions": dimensions})

    def test_registry_resolves_nested_and_symlink_paths(self) -> None:
        nested = self.project / "src/feature"; nested.mkdir(parents=True)
        link = self.root / "project-link"; link.symlink_to(self.project, target_is_directory=True)
        self.assertEqual(resolve_project(str(nested))["id"], self.registration["id"])
        self.assertEqual(resolve_project(str(link / "src"))["id"], self.registration["id"])

    def test_concurrent_prepare_is_deduplicated(self) -> None:
        payload = {"source": "codex", "raw_session_id": "same", "original_prompt": "do it",
                   "task_brief": self.brief(), "approved": True}
        threads = [threading.Thread(target=prepare_task, args=(self.registration["id"], payload)) for _ in range(10)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        lines = (self.data / "tasks" / f"{self.registration['id']}.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), 1)

    def test_hook_ignores_unregistered_projects_and_internal_runs(self) -> None:
        other = self.root / "other"; other.mkdir()
        self.assertFalse(record_hook("claude", {"cwd": str(other)})[0])
        with patch.dict(os.environ, {"AI_WORK_WATCHER_INTERNAL_RUN": "1"}):
            self.assertFalse(record_hook("codex", {"cwd": str(self.project)})[0])

    def test_all_public_schemas_parse_and_trend_schema_forbids_overall_score(self) -> None:
        schemas = Path(__file__).parents[1] / "schemas"
        values = [json.loads(path.read_text()) for path in schemas.glob("*.schema.json")]
        self.assertEqual(len(values), 5)
        trend = next(item for item in values if item.get("title") == "TrendReport v1")
        self.assertEqual(trend["not"], {"required": ["overall_score"]})

    def test_prune_removes_complete_task_units_after_retention(self) -> None:
        task_id = self._complete("old-task")
        path = self.data / "tasks" / f"{self.registration['id']}.jsonl"
        records = [json.loads(line) for line in path.read_text().splitlines()]
        for record in records:
            if record["task_id"] == task_id: record["timestamp"] = "2020-01-01T00:00:00+00:00"
        path.write_text("".join(json.dumps(record) + "\n" for record in records))
        kept, removed = prune_tasks(180)
        self.assertEqual((kept, removed), (0, 2))


if __name__ == "__main__":
    unittest.main()
