from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from waterctl.hooks import record_hook
from waterctl.install import MARKER_START, doctor, install, uninstall
from waterctl.paths import guidance_path, recommendations_path, water_home
from waterctl.projects import add_project, resolve_project
from waterctl.review import DIMENSIONS, ReviewError, run_weekly
from waterctl.schema import ValidationError, normalize_event
from waterctl.store import append_event, event_path, prune_events, recommendation_states
from waterctl.cli import _transition_recommendation


class WaterTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="water-test-")
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.data = self.root / "data"
        self.home.mkdir()
        self.project = self.root / "project"
        self.project.mkdir()
        self.environment = patch.dict(os.environ, {"HOME": str(self.home), "WATER_HOME": str(self.data)}, clear=False)
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()
        self.temporary.cleanup()

    def register(self, path: Path | None = None, name: str = "project") -> dict:
        return add_project(str(path or self.project), name=name)

    def event(self, project_id: str, **overrides: object) -> dict:
        data = {
            "source_terminal": "codex",
            "model": "gpt-test",
            "source_version": "1",
            "raw_session_id": "session-1",
            "event_type": "session_summary",
            "goal": "Complete the requested change",
            "actions": ["Inspected implementation", "Ran tests"],
            "outcome": "Change verified",
            "status": "completed",
            "evidence": [{"kind": "test", "summary": "10 passed"}],
            "blockers": [],
            "risks": [],
            "metrics": {"test_count": 10},
            "tags": ["test"],
            "confidence": 0.9,
        }
        data.update(overrides)
        return normalize_event(data, project_id)


class SchemaAndPrivacyTests(WaterTestCase):
    def test_normalizes_hashes_and_redacts_sensitive_text(self) -> None:
        project = self.register()
        event = self.event(
            project["id"],
            goal="Contact dev@example.com using token=ghp_abcdefghijklmnopqrstuvwxyz1234",
        )
        self.assertNotIn("dev@example.com", event["goal"])
        self.assertNotIn("ghp_", event["goal"])
        self.assertTrue(event["session_id"].startswith("session-"))
        self.assertNotEqual(event["session_id"], "session-1")
        self.assertGreater(sum(event["redaction_summary"].values()), 0)

    def test_rejects_unknown_version_illegal_status_and_long_text(self) -> None:
        project = self.register()
        for override in ({"schema_version": 2}, {"status": "perfect"}, {"goal": "x" * 2001}):
            with self.subTest(override=override), self.assertRaises(ValidationError):
                self.event(project["id"], **override)

    def test_rejects_unknown_fields(self) -> None:
        project = self.register()
        with self.assertRaises(ValidationError):
            normalize_event({"goal": "x", "transcript": "full conversation"}, project["id"])

    def test_rejects_transcript_shaped_nested_evidence_and_text_metrics(self) -> None:
        project = self.register()
        with self.assertRaises(ValidationError):
            self.event(project["id"], evidence=[{"transcript": "full conversation"}])
        with self.assertRaises(ValidationError):
            self.event(project["id"], metrics={"terminal_output": "full output"})


class ProjectAndStorageTests(WaterTestCase):
    def test_explicit_registry_resolves_nested_and_symlink_paths(self) -> None:
        project = self.register()
        nested = self.project / "src" / "feature"
        nested.mkdir(parents=True)
        link = self.root / "project-link"
        link.symlink_to(self.project, target_is_directory=True)
        self.assertEqual(resolve_project(str(nested))["id"], project["id"])
        self.assertEqual(resolve_project(str(link / "src"))["id"], project["id"])
        self.assertIsNone(resolve_project(str(self.root / "unregistered")))

    def test_duplicate_and_concurrent_writes_are_safe(self) -> None:
        project = self.register()
        events = [self.event(project["id"], raw_session_id=f"session-{index}") for index in range(20)]
        threads = [threading.Thread(target=append_event, args=(event,)) for event in events]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertFalse(append_event(events[0]))
        lines = event_path(project["id"]).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 20)
        self.assertEqual(len({json.loads(line)["event_id"] for line in lines}), 20)

    def test_prune_removes_only_expired_event_details(self) -> None:
        project = self.register()
        old = self.event(project["id"], raw_session_id="old", timestamp="2020-01-01T00:00:00+00:00")
        current = self.event(project["id"], raw_session_id="current", timestamp=datetime.now(timezone.utc).isoformat())
        append_event(old)
        append_event(current)
        kept, removed = prune_events(180)
        self.assertEqual((kept, removed), (1, 1))
        self.assertEqual(json.loads(event_path(project["id"]).read_text(encoding="utf-8"))["event_id"], current["event_id"])


class HookAndInstallTests(WaterTestCase):
    def test_codex_and_claude_hooks_create_equivalent_fallback_shape(self) -> None:
        first = self.register(self.project, "first")
        second_path = self.root / "second"
        second_path.mkdir()
        second = self.register(second_path, "second")
        codex_payload = {"session_id": "codex-session", "cwd": str(self.project), "model": "gpt-test", "version": "1"}
        claude_payload = {"session_id": "claude-session", "cwd": str(second_path), "model": "claude-test", "version": "2", "transcript_path": "/not/read"}
        self.assertTrue(record_hook("codex", codex_payload)[0])
        self.assertTrue(record_hook("claude", claude_payload)[0])
        left = json.loads(event_path(first["id"]).read_text(encoding="utf-8"))
        right = json.loads(event_path(second["id"]).read_text(encoding="utf-8"))
        for key in ("schema_version", "event_type", "status", "confidence", "actions", "metrics"):
            self.assertEqual(left[key], right[key])
        self.assertNotIn("transcript", json.dumps(right))

    def test_hook_ignores_unregistered_and_internal_runs(self) -> None:
        self.assertFalse(record_hook("codex", {"cwd": str(self.project)})[0])
        self.register()
        with patch.dict(os.environ, {"WATER_INTERNAL_RUN": "1"}):
            self.assertFalse(record_hook("codex", {"cwd": str(self.project)})[0])

    def test_install_is_idempotent_and_uninstall_preserves_user_config(self) -> None:
        claude_settings = self.home / ".claude" / "settings.json"
        claude_settings.parent.mkdir(parents=True)
        claude_settings.write_text('{"theme":"dark","hooks":{"Stop":[]}}\n', encoding="utf-8")
        launch_result = type("Result", (), {"returncode": 0, "stderr": ""})()
        real_which = __import__("shutil").which

        def fake_which(command: str) -> str | None:
            if command in {"launchctl", "codex", "claude"}:
                return f"/usr/bin/{command}"
            return real_which(command)

        with patch("waterctl.install.shutil.which", side_effect=fake_which), \
             patch("waterctl.install.subprocess.run", return_value=launch_result):
            install()
            first_settings = claude_settings.read_text(encoding="utf-8")
            first_backups = list(claude_settings.parent.glob("settings.json.water-backup-*"))
            install()
            doctor_checks = doctor()
        self.assertEqual(claude_settings.read_text(encoding="utf-8"), first_settings)
        self.assertEqual(len(list(claude_settings.parent.glob("settings.json.water-backup-*"))), len(first_backups))
        self.assertEqual(json.loads(first_settings)["theme"], "dark")
        self.assertIn(MARKER_START, (self.home / ".codex" / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertTrue(all(passed for passed, _ in doctor_checks))
        with patch("waterctl.install.shutil.which", side_effect=fake_which), \
             patch("waterctl.install.subprocess.run", return_value=launch_result):
            uninstall()
        self.assertEqual(json.loads(claude_settings.read_text(encoding="utf-8"))["theme"], "dark")
        self.assertNotIn(MARKER_START, (self.home / ".codex" / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertTrue(self.data.exists())


class ReviewAndRecommendationTests(WaterTestCase):
    def review_result(self, event_id: str) -> dict:
        score = {"score": 4, "confidence": 0.8, "evidence_ids": [event_id], "rationale": "Supported by verification evidence"}
        return {
            "summary": "Delivery was reliable; verification can become more consistent.",
            "scores": {dimension: dict(score) for dimension in DIMENSIONS},
            "recommendations": [{
                "title": "Standardize focused verification",
                "scope": "global",
                "category": "verification",
                "evidence_ids": [event_id],
                "diagnosis": "Verification evidence varies by session.",
                "proposed_change": "Record the focused test command and result before finalizing.",
                "expected_effect": "Higher verification consistency.",
                "impact": "high",
                "confidence": 0.8,
                "effort": "low",
                "validation_metric": "Verified sessions exceed 90% for three weeks.",
                "rollback_condition": "Median cycle time rises by more than 15%.",
            }],
            "cross_project_patterns": ["Focused checks correlate with complete outcomes."],
        }

    def test_weekly_report_is_traceable_and_recommendation_promotes_after_three_verifications(self) -> None:
        project = self.register()
        event = self.event(project["id"], timestamp="2026-08-11T03:00:00+00:00")
        append_event(event)
        with patch("waterctl.review._run_codex", return_value=self.review_result(event["event_id"])):
            report = run_weekly("codex", "2026-W33")
        contents = report.read_text(encoding="utf-8")
        self.assertIn(event["event_id"], contents)
        states = recommendation_states()
        identifier = next(iter(states))
        _transition_recommendation(identifier, "accept", "trial")
        self.assertNotIn(identifier, guidance_path().read_text(encoding="utf-8"))
        for _ in range(3):
            _transition_recommendation(identifier, "verify", "passed", "pass")
        self.assertIn(identifier, guidance_path().read_text(encoding="utf-8"))

    def test_empty_week_generates_no_scores_or_recommendations(self) -> None:
        self.register()
        report = run_weekly("auto", "2026-W33")
        self.assertIn("No registered project events", report.read_text(encoding="utf-8"))
        self.assertFalse(recommendations_path().exists())

    def test_unknown_evidence_is_rejected(self) -> None:
        project = self.register()
        event = self.event(project["id"], timestamp="2026-08-11T03:00:00+00:00")
        append_event(event)
        result = self.review_result("evt-does-not-exist")
        with patch("waterctl.review._run_codex", return_value=result):
            with self.assertRaises(Exception):
                run_weekly("codex", "2026-W33")

    def test_free_text_and_unknown_project_scopes_are_rejected(self) -> None:
        project = self.register()
        event = self.event(project["id"], timestamp="2026-08-11T03:00:00+00:00")
        append_event(event)
        for scope in ("weekly review pipeline", "project:not-registered"):
            result = self.review_result(event["event_id"])
            result["recommendations"][0]["scope"] = scope
            with self.subTest(scope=scope), patch("waterctl.review._run_codex", return_value=result):
                with self.assertRaises(ReviewError):
                    run_weekly("codex", "2026-W33")

    def test_auto_provider_honors_project_preference(self) -> None:
        project = add_project(str(self.project), name="project", provider="claude")
        event = self.event(project["id"], timestamp="2026-08-11T03:00:00+00:00")
        append_event(event)
        with patch("waterctl.review._run_claude", return_value=self.review_result(event["event_id"])) as claude_run, \
             patch("waterctl.review._run_codex") as codex_run:
            run_weekly("auto", "2026-W33")
        claude_run.assert_called_once()
        codex_run.assert_not_called()

    def test_auto_provider_falls_back_from_codex_to_claude(self) -> None:
        project = self.register()
        event = self.event(project["id"], timestamp="2026-08-11T03:00:00+00:00")
        append_event(event)
        with patch("waterctl.review._run_codex", side_effect=ReviewError("unavailable")) as codex_run, \
             patch("waterctl.review._run_claude", return_value=self.review_result(event["event_id"])) as claude_run:
            run_weekly("auto", "2026-W33")
        codex_run.assert_called_once()
        claude_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
