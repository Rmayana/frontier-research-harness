from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from frontier_research_harness.research_runtime import ResearchRunner, RuntimeStore, build_spec
from frontier_research_harness.research_settings import resolve_execution
from tests.test_research_runtime import FakeHost


class CatalogHost(FakeHost):
    def __init__(self):
        super().__init__()
        self.configured = "research-model"
        self.efforts = ["low", "high", "ultra"]
        self.confirmed_effort = "ultra"

    def call(self, method, params):
        if method in {"config/read", "model/list", "thread/start", "thread/resume"}:
            self.calls.append((method, params.copy()))
            if method == "config/read": return {"config": {"model": self.configured}}
            if method == "model/list":
                if "cursor" not in params:
                    return {"data": [{"model": "other", "isDefault": True}], "nextCursor": "next"}
                return {"data": [{"id": "research-model", "model": "research-model",
                                  "supportedReasoningEfforts": [{"reasoningEffort": e} for e in self.efforts]}]}
            return {"thread": {"id": "owned"}, "model": "research-model", "reasoningEffort": self.confirmed_effort}
        return super().call(method, params)


class ResearchSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "goal.json").write_text(json.dumps({"north_star": "Synthetic goal"}), encoding="utf-8")
        (self.root / "AGENTS.md").write_text("Research instructions", encoding="utf-8")
        self.store = RuntimeStore(self.root / "runtime.db")
        spec = build_spec(self.root, self.root / "research.db", token_budget=1000,
                          reasoning_effort="highest_supported")
        self.run_id = self.store.prepare(spec)["run_id"]
        self.owner = self.store.acquire(self.run_id)
        self.host = CatalogHost()
        self.runner = ResearchRunner(self.store, self.host)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_configured_model_and_paginated_catalog_apply_only_thread_override(self):
        run = self.runner.start(self.run_id, self.owner)
        request = next(p for m, p in self.host.calls if m == "thread/start")
        self.assertEqual(request["model"], "research-model")
        self.assertEqual(request["config"], {"model_reasoning_effort": "ultra"})
        self.assertEqual(run["execution"]["verification"], "confirmed")
        self.assertEqual(len(run["execution"]["instruction_sources"]), 1)
        self.assertFalse(any("write" in m for m, _ in self.host.calls))

    def test_unknown_catalog_effort_prevents_thread_creation(self):
        self.host.efforts.append("future-level")
        with self.assertRaisesRegex(ValueError, "cannot order"):
            self.runner.start(self.run_id, self.owner)
        self.assertNotIn("thread/start", [m for m, _ in self.host.calls])

    def test_unsupported_explicit_effort_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not advertise"):
            resolve_execution(self.host, {"project_dir": str(self.root), "reasoning_effort": "max"})

    def test_missing_or_mismatched_confirmation_never_activates_goal(self):
        self.host.confirmed_effort = None
        with self.assertRaisesRegex(RuntimeError, "confirmation"):
            self.runner.start(self.run_id, self.owner)
        self.assertIsNone(self.host.goal)
        self.assertEqual(self.store.get(self.run_id)["state"], "NEEDS_ATTENTION")

    def test_resume_pins_original_settings_and_records_source_changes(self):
        first = self.runner.start(self.run_id, self.owner)
        self.runner.pause(self.run_id, self.owner)
        self.host.configured = "other"
        (self.root / "AGENTS.md").write_text("Changed instructions", encoding="utf-8")
        before = len(self.host.calls)
        resumed = self.runner.resume(self.run_id, self.owner)
        calls = self.host.calls[before:]
        self.assertNotIn("model/list", [m for m, _ in calls])
        request = next(p for m, p in calls if m == "thread/resume")
        self.assertEqual(request["config"], {"model_reasoning_effort": "ultra"})
        self.assertEqual(resumed["native_goal"]["status"], "paused")
        self.assertNotEqual(first["execution"]["instruction_sources"],
                            resumed["execution"]["resume_instruction_sources"])

    def test_resume_mismatch_parks_active_goal(self):
        self.runner.start(self.run_id, self.owner)
        self.host.confirmed_effort = "low"
        with self.assertRaisesRegex(RuntimeError, "confirmation"):
            self.runner.resume(self.run_id, self.owner)
        self.assertEqual(self.host.goal["status"], "paused")
        self.assertEqual(self.store.get(self.run_id)["state"], "NEEDS_ATTENTION")

    def test_inherit_does_not_query_or_override_host(self):
        resolved = resolve_execution(self.host, {"reasoning_effort": "inherit"})
        self.assertIsNone(resolved["effort"])
        self.assertEqual(self.host.calls, [])


if __name__ == "__main__": unittest.main()
