from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from frontier_research_harness.codex_app_server import HostRejected
from frontier_research_harness.research_runtime import RuntimeStore, ResearchRunner, build_spec


class FakeHost:
    runtime_identity = "offline-test-host"

    def __init__(self):
        self.calls = []; self.events = []; self.goal = None; self.fail = None

    def call(self, method, params):
        self.calls.append((method, params.copy()))
        if self.fail == method: raise TimeoutError("uncertain delivery")
        if method == "thread/start": return {"thread": {"id": "owned"}}
        if method == "thread/resume": return {"thread": {"id": "owned"}}
        if method == "thread/goal/set":
            self.goal = {**(self.goal or {"tokensUsed": 0}), **params}
            return {"goal": self.goal.copy()}
        if method == "thread/goal/get": return {"goal": self.goal.copy() if self.goal else None}
        if method == "turn/steer": return {"turnId": params["expectedTurnId"]}
        if method == "turn/interrupt": return {}
        raise AssertionError(method)

    def drain_events(self):
        events, self.events = self.events, []
        return events

    def respond(self, request_id, result): self.calls.append(("respond", {"id": request_id, "result": result}))


class ResearchRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        (self.root / "goal.json").write_text(json.dumps({"goal_id": "test", "north_star": "Synthetic research goal"}), encoding="utf-8")
        self.store = RuntimeStore(self.root / "runtime.db")
        self.run_id = self.store.prepare(build_spec(self.root, self.root / "research.db", token_budget=1000, time_budget_seconds=600))["run_id"]
        self.owner = self.store.acquire(self.run_id); self.host = FakeHost(); self.runner = ResearchRunner(self.store, self.host)

    def tearDown(self): self.store.close(); self.temp.cleanup()

    def start(self): return self.runner.start(self.run_id, self.owner)

    def test_one_native_controller_no_synthetic_turns(self):
        run = self.start()
        self.assertEqual(run["state"], "RUNNING")
        self.assertEqual([m for m, _ in self.host.calls], ["thread/start", "thread/goal/set", "thread/goal/set"])
        self.assertEqual(run["runtime_identity"], "offline-test-host")
        self.assertIn(str(self.root / "research.db"), self.host.calls[0][1]["developerInstructions"].replace("\\\\", "\\"))

    def test_second_owner_fenced_and_clean_reopen_allowed(self):
        with RuntimeStore(self.store.path) as other:
            with self.assertRaisesRegex(RuntimeError, "another owner"): other.acquire(self.run_id)
            self.store.release(self.run_id, self.owner)
            token = other.acquire(self.run_id)
            with self.assertRaisesRegex(RuntimeError, "fencing"): self.store.assert_owner(self.run_id, self.owner)
            other.release(self.run_id, token)

    def test_crash_marks_attention_and_resume_does_not_dispatch(self):
        self.start(); self.store.close()
        self.store = RuntimeStore(self.root / "runtime.db"); self.owner = self.store.acquire(self.run_id)
        self.runner = ResearchRunner(self.store, self.host); calls = len(self.host.calls)
        self.assertEqual(self.runner.resume(self.run_id, self.owner)["state"], "NEEDS_ATTENTION")
        self.assertEqual(len(self.host.calls), calls)
        run = self.runner.recover(self.run_id, self.owner, prior_host_stopped=True)
        self.assertEqual(run["native_goal"]["status"], "paused")

    def test_uncertain_start_is_not_replayed(self):
        self.host.fail = "thread/start"
        with self.assertRaises(TimeoutError): self.start()
        self.runner.resume(self.run_id, self.owner)
        self.assertEqual(len(self.host.calls), 1)
        self.assertIsNotNone(self.store.get(self.run_id)["pending_operation"])

    def test_pause_and_explicit_activation_preserve_usage(self):
        self.start(); self.host.goal["tokensUsed"] = 42
        self.runner.pause(self.run_id, self.owner)
        run = self.runner.resume(self.run_id, self.owner)
        self.assertEqual(run["native_goal"]["status"], "paused")
        self.assertEqual(self.runner.activate(self.run_id, self.owner)["native_goal"]["tokensUsed"], 42)
        self.assertNotIn("objective", self.host.calls[-1][1])

    def test_time_budget_never_resets_on_resume(self):
        self.start()
        started = (datetime.now(timezone.utc) - timedelta(seconds=601)).isoformat()
        with self.store.connection: self.store.connection.execute("UPDATE research_runs SET started_at=?", (started,))
        self.assertEqual(self.runner.resume(self.run_id, self.owner)["native_goal"]["status"], "paused")
        with self.assertRaisesRegex(RuntimeError, "time budget"): self.runner.activate(self.run_id, self.owner)
        self.assertEqual(self.store.get(self.run_id)["started_at"], started)

    def test_budget_limited_or_complete_not_reactivated(self):
        self.start()
        for status in ("complete", "budgetLimited", "usageLimited", "blocked"):
            self.host.goal["status"] = status
            count = len(self.host.calls)
            self.runner.resume(self.run_id, self.owner)
            self.assertEqual([m for m, _ in self.host.calls[count:]], ["thread/goal/get"])

    def test_child_events_do_not_replace_root_state_or_double_count_usage(self):
        self.start()
        root = {"eventId": "root", "method": "turn/started", "params": {"threadId": "owned", "turn": {"id": "r"}}}
        self.host.events = [root, root,
            {"method": "turn/started", "params": {"threadId": "child", "turn": {"id": "c"}}},
            {"method": "thread/goal/updated", "params": {"threadId": "child", "goal": {"status": "complete"}}},
            {"method": "thread/tokenUsage/updated", "params": {"threadId": "owned", "tokenUsage": {"total": 42}}}]
        self.runner.consume(self.run_id, self.owner)
        run = self.store.get(self.run_id)
        self.assertEqual(run["active_turn_id"], "r"); self.assertEqual(run["native_goal"]["status"], "active")
        self.assertEqual(run["usage"], {"total": 42}); self.assertEqual(len(self.store.events(self.run_id)), 4)
        delta = {"method": "item/agentMessage/delta", "params": {"delta": "ha"}}
        self.host.events = [delta, delta]; self.runner.consume(self.run_id, self.owner)
        self.assertEqual(len(self.store.events(self.run_id)), 6)

    def test_human_direction_waits_idle_gap_then_is_retained_and_delivered(self):
        self.start(); seq = self.store.submit_control(self.run_id, "steer", {"text": "Question the mechanism"})
        self.runner.process_controls(self.run_id, self.owner)
        self.assertEqual(self.store.controls(self.run_id)[0]["status"], "PENDING")
        self.host.events = [{"method": "turn/started", "params": {"threadId": "owned", "turn": {"id": "t"}}}]
        self.runner.consume(self.run_id, self.owner); self.runner.process_controls(self.run_id, self.owner)
        control = self.store.controls(self.run_id)[0]
        self.assertEqual(control["sequence"], seq); self.assertEqual(control["status"], "DONE")
        self.assertIn("research_entry", json.loads(control["result_json"]))
        self.assertEqual(self.host.calls[-1][0], "turn/steer")

    def test_server_request_never_auto_approved(self):
        self.start(); self.host.events = [{"id": 7, "method": "item/commandExecution/requestApproval", "params": {"threadId": "owned"}}]
        self.runner.consume(self.run_id, self.owner)
        self.assertEqual(self.store.get(self.run_id)["state"], "WAITING_FOR_USER")
        self.assertNotIn("respond", [m for m, _ in self.host.calls])
        self.store.submit_control(self.run_id, "respond", {"request_id": "7", "result": {"decision": "decline"}})
        self.runner.process_controls(self.run_id, self.owner)
        self.assertEqual(self.host.calls[-1][1]["result"], {"decision": "decline"})
        self.assertFalse(self.store.get(self.run_id)["requests"])

    def test_pause_consumes_in_flight_start_before_interrupting(self):
        self.start()
        self.host.events = [{"method": "turn/started", "params": {"threadId": "owned", "turn": {"id": "late"}}}]
        self.runner.pause(self.run_id, self.owner)
        self.assertIn(("turn/interrupt", {"threadId": "owned", "turnId": "late"}), self.host.calls)

    def test_uncertain_steering_is_retained_not_resent(self):
        self.start()
        self.host.events = [{"method": "turn/started", "params": {"threadId": "owned", "turn": {"id": "t"}}}]
        self.runner.consume(self.run_id, self.owner)
        self.host.fail = "turn/steer"
        self.store.submit_control(self.run_id, "steer", {"text": "Alternative explanation?"})
        self.assertFalse(self.runner.process_controls(self.run_id, self.owner))
        self.runner.process_controls(self.run_id, self.owner)
        self.assertEqual(sum(m == "turn/steer" for m, _ in self.host.calls), 1)
        self.assertEqual(self.store.get(self.run_id)["state"], "NEEDS_ATTENTION")
        self.assertEqual(self.store.controls(self.run_id)[0]["status"], "FAILED")

    def test_disconnect_and_goal_drift_are_not_completion(self):
        self.start(); self.host.events = [{"method": "transport/closed", "params": {}}]
        self.runner.consume(self.run_id, self.owner)
        self.assertEqual(self.store.get(self.run_id)["state"], "NEEDS_ATTENTION")
        (self.root / "goal.json").write_text('{"north_star":"changed"}', encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "goal file changed"): self.runner.resume(self.run_id, self.owner)


if __name__ == "__main__": unittest.main()
