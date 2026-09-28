"""Durable, opt-in operation layer for runner-owned native Codex goals.

This module records transport state.  Native Codex owns continuation and Codex
owns every scientific decision; no scientific scheduler or completion rule lives
here.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4
from frontier_research_harness.codex_app_server import HostRejected

from frontier_research_harness.scientific_contracts import canonical_sha256
from frontier_research_harness.research_settings import (
    EFFORT_CHOICES, instruction_identity, observed_execution, resolve_execution, thread_overrides,
)

NATIVE_GOAL_STATES = {"active", "paused", "blocked", "usageLimited", "budgetLimited", "complete"}
NON_REACTIVATING_STATES = NATIVE_GOAL_STATES - {"active"}
TERMINAL_EVENT_METHODS = {"turn/completed", "turn/failed", "thread/goal/updated"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class NativeHost(Protocol):
    runtime_identity: str

    def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]: ...
    def drain_events(self) -> list[dict[str, Any]]: ...
    def respond(self, request_id: int | str, result: dict[str, Any]) -> None: ...


@dataclass(frozen=True)
class RunSpec:
    project_dir: str
    research_database: str
    goal_path: str
    goal_id: str
    goal_digest: str
    objective: str
    runtime: str
    token_budget: int | None
    time_budget_seconds: int | None
    model: str | None = None
    sandbox: str = "workspace-write"
    python_executable: str = sys.executable
    reasoning_effort: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class RuntimeStore:
    """SQLite record store with transactional owner fencing."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self._locks: dict[str, Any] = {}
        self.connection.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS research_runs(
          run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          spec_json TEXT NOT NULL, state TEXT NOT NULL, owner_token TEXT,
          managed_thread_id TEXT, active_turn_id TEXT, native_goal_json TEXT,
          pending_operation_json TEXT, attention_reason TEXT,
          usage_json TEXT, last_event_sequence INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS research_run_events(
          run_id TEXT NOT NULL, sequence INTEGER NOT NULL, event_key TEXT NOT NULL,
          received_at TEXT NOT NULL, method TEXT NOT NULL, event_json TEXT NOT NULL,
          PRIMARY KEY(run_id,event_key), UNIQUE(run_id,sequence),
          FOREIGN KEY(run_id) REFERENCES research_runs(run_id)
        );
        CREATE TABLE IF NOT EXISTS research_run_operations(
          operation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, created_at TEXT NOT NULL,
          kind TEXT NOT NULL, request_json TEXT NOT NULL, status TEXT NOT NULL,
          response_json TEXT, FOREIGN KEY(run_id) REFERENCES research_runs(run_id)
        );
        CREATE TABLE IF NOT EXISTS research_run_controls(
          sequence INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
          created_at TEXT NOT NULL, kind TEXT NOT NULL, payload_json TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'PENDING', result_json TEXT,
          FOREIGN KEY(run_id) REFERENCES research_runs(run_id)
        );
        """)
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(research_runs)")}
        for name, kind in {"started_at": "TEXT", "runtime_identity": "TEXT", "requests_json": "TEXT", "execution_json": "TEXT"}.items():
            if name not in columns: self.connection.execute(f"ALTER TABLE research_runs ADD COLUMN {name} {kind}")
        self.connection.commit()

    def close(self) -> None:
        # Do not erase durable ownership on an unclean exit; next owner must reconcile.
        for lock in self._locks.values(): lock.close()
        self._locks.clear()
        self.connection.close()
    def __enter__(self) -> "RuntimeStore": return self
    def __exit__(self, *_: object) -> None: self.close()

    def prepare(self, spec: RunSpec) -> dict[str, Any]:
        run_id = str(uuid4()); now = _now()
        with self.connection:
            self.connection.execute(
                "INSERT INTO research_runs(run_id,created_at,updated_at,spec_json,state,usage_json) VALUES(?,?,?,?,?,?)",
                (run_id, now, now, json.dumps(spec.as_dict(), ensure_ascii=False), "PREPARED", "null"))
        return self.get(run_id)

    def get(self, run_id: str) -> dict[str, Any]:
        row = self.connection.execute("SELECT * FROM research_runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None: raise KeyError(f"unknown run: {run_id}")
        result = dict(row)
        for key in ("spec_json", "native_goal_json", "pending_operation_json", "usage_json", "requests_json", "execution_json"):
            result[key.removesuffix("_json")] = json.loads(result.pop(key)) if result[key] else None
        return result

    def acquire(self, run_id: str, owner: str | None = None) -> str:
        self.get(run_id)
        if run_id in self._locks: raise RuntimeError("run already acquired on this connection")
        # OS locks survive competing connections but release automatically on process death.
        lock = open(self.path.with_name(self.path.name + "." + canonical_sha256(run_id) + ".lock"), "a+b")
        if lock.tell() == 0: lock.write(b"0"); lock.flush()
        lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            lock.close()
            raise RuntimeError("run is controlled by another owner") from exc
        owner = owner or str(uuid4())
        try:
            with self.connection:
                row = self.connection.execute("SELECT owner_token FROM research_runs WHERE run_id=?", (run_id,)).fetchone()
                if row[0]:
                    self.connection.execute("UPDATE research_runs SET state='NEEDS_ATTENTION',attention_reason=? WHERE run_id=?",
                                            ("Prior controller ended without releasing ownership; confirm its host is stopped before recovery.", run_id))
                self.connection.execute("UPDATE research_runs SET owner_token=?,updated_at=? WHERE run_id=?", (owner, _now(), run_id))
            self._locks[run_id] = lock
        except BaseException:
            lock.close()
            raise
        return owner

    def release(self, run_id: str, owner: str) -> None:
        with self.connection:
            self.assert_owner(run_id, owner)
            self.connection.execute("UPDATE research_runs SET owner_token=NULL WHERE run_id=?", (run_id,))
        self._locks.pop(run_id).close()

    def assert_owner(self, run_id: str, owner: str) -> None:
        row = self.connection.execute("SELECT owner_token FROM research_runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None or row[0] != owner or run_id not in self._locks: raise RuntimeError("owner fencing check failed")

    def begin_operation(self, run_id: str, owner: str, kind: str, request: dict[str, Any]) -> str:
        operation_id = str(uuid4())
        with self.connection:
            self.assert_owner(run_id, owner)
            if self.get(run_id)["pending_operation"] and kind != "pause":
                raise RuntimeError("unacknowledged dispatch must not be replayed")
            payload = json.dumps(request, ensure_ascii=False)
            self.connection.execute("INSERT INTO research_run_operations VALUES(?,?,?,?,?,?,NULL)",
                                    (operation_id, run_id, _now(), kind, payload, "DISPATCHING"))
            self.connection.execute("UPDATE research_runs SET pending_operation_json=?,updated_at=? WHERE run_id=?",
                                    (json.dumps({"operation_id": operation_id, "kind": kind, "request": request}, ensure_ascii=False), _now(), run_id))
        return operation_id

    def acknowledge(self, run_id: str, owner: str, operation_id: str, response: dict[str, Any], **fields: Any) -> None:
        allowed = {"state", "managed_thread_id", "active_turn_id", "native_goal_json", "attention_reason", "started_at", "runtime_identity", "requests_json", "execution_json"}
        if set(fields) - allowed: raise ValueError("unsupported run fields")
        with self.connection:
            self.assert_owner(run_id, owner)
            self.connection.execute("UPDATE research_run_operations SET status='ACKNOWLEDGED',response_json=? WHERE operation_id=? AND run_id=?",
                                    (json.dumps(response, ensure_ascii=False), operation_id, run_id))
            assignments = ["pending_operation_json=NULL", "updated_at=?"]
            values: list[Any] = [_now()]
            for key, value in fields.items():
                assignments.append(f"{key}=?")
                values.append(json.dumps(value, ensure_ascii=False) if key.endswith("_json") else value)
            values.append(run_id)
            self.connection.execute(f"UPDATE research_runs SET {','.join(assignments)} WHERE run_id=?", values)

    def needs_attention(self, run_id: str, owner: str, reason: str) -> None:
        with self.connection:
            self.assert_owner(run_id, owner)
            self.connection.execute("UPDATE research_runs SET state='NEEDS_ATTENTION',attention_reason=?,updated_at=? WHERE run_id=?", (reason, _now(), run_id))

    def record_event(self, run_id: str, owner: str, event: dict[str, Any]) -> bool:
        method = str(event.get("method", "unknown")); params = event.get("params", {})
        # Identical text deltas can legitimately repeat. Only host-supplied IDs deduplicate.
        identity = event.get("eventId") or params.get("eventId") or str(uuid4())
        with self.connection:
            self.assert_owner(run_id, owner)
            row = self.connection.execute("SELECT last_event_sequence,usage_json FROM research_runs WHERE run_id=?", (run_id,)).fetchone()
            try:
                sequence = int(row[0]) + 1
                self.connection.execute("INSERT INTO research_run_events VALUES(?,?,?,?,?,?)",
                    (run_id, sequence, str(identity), _now(), method, json.dumps(event, ensure_ascii=False)))
            except sqlite3.IntegrityError:
                return False
            usage = params.get("usage") or params.get("tokenUsage")
            usage_json = row[1]
            if usage is not None: usage_json = json.dumps(usage, ensure_ascii=False)
            current = self.get(run_id)
            root_event = params.get("threadId") in (None, current["managed_thread_id"])
            goal = params.get("goal") if root_event and method == "thread/goal/updated" else None
            goal_json = json.dumps(goal, ensure_ascii=False) if goal is not None else None
            turn_id = params.get("turnId") or (params.get("turn") or {}).get("id")
            active = self.get(run_id).get("active_turn_id")
            if root_event and method == "turn/started": active = turn_id
            elif root_event and method in {"turn/completed", "turn/failed"} and turn_id == active: active = None
            if not root_event: usage_json = row[1]
            self.connection.execute("UPDATE research_runs SET last_event_sequence=?,usage_json=?,native_goal_json=COALESCE(?,native_goal_json),active_turn_id=?,updated_at=? WHERE run_id=?",
                                    (sequence, usage_json, goal_json, active, _now(), run_id))
            if "id" in event and "method" in event:
                requests = current.get("requests") or {}
                requests[str(event["id"])] = event
                self.connection.execute("UPDATE research_runs SET requests_json=?,state='WAITING_FOR_USER' WHERE run_id=?",
                                        (json.dumps(requests, ensure_ascii=False), run_id))
            if method == "transport/closed":
                self.needs_attention(run_id, owner, "Native transport closed; no automatic replay or restart.")
        return True

    def events(self, run_id: str, after: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        self.get(run_id)
        if after < 0 or not 1 <= limit <= 1000: raise ValueError("invalid event page bounds")
        rows = self.connection.execute("SELECT sequence,received_at,method,event_json FROM research_run_events WHERE run_id=? AND sequence>? ORDER BY sequence LIMIT ?", (run_id, after, limit)).fetchall()
        return [{"sequence": r[0], "received_at": r[1], "method": r[2], "event": json.loads(r[3])} for r in rows]

    def submit_control(self, run_id: str, kind: str, payload: dict[str, Any] | None = None) -> int:
        if kind not in {"pause", "steer", "stop", "respond"}: raise ValueError("unknown control")
        if kind == "steer" and not str((payload or {}).get("text", "")).strip(): raise ValueError("steering text cannot be empty")
        self.get(run_id)
        with self.connection:
            cursor = self.connection.execute("INSERT INTO research_run_controls(run_id,created_at,kind,payload_json) VALUES(?,?,?,?)", (run_id, _now(), kind, json.dumps(payload or {}, ensure_ascii=False)))
        return int(cursor.lastrowid)

    def controls(self, run_id: str, after: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        self.get(run_id)
        if after < 0 or not 1 <= limit <= 1000: raise ValueError("invalid control page bounds")
        rows = self.connection.execute("SELECT * FROM research_run_controls WHERE run_id=? AND sequence>? ORDER BY sequence LIMIT ?", (run_id, after, limit))
        return [dict(row) for row in rows]

    def pending_controls(self, run_id: str, owner: str) -> list[dict[str, Any]]:
        self.assert_owner(run_id, owner)
        rows = self.connection.execute("SELECT sequence,kind,payload_json FROM research_run_controls WHERE run_id=? AND status='PENDING' ORDER BY sequence", (run_id,)).fetchall()
        return [{"sequence": r[0], "kind": r[1], "payload": json.loads(r[2])} for r in rows]

    def finish_control(self, run_id: str, owner: str, sequence: int, result: dict[str, Any], *, failed: bool = False) -> None:
        with self.connection:
            self.assert_owner(run_id, owner)
            self.connection.execute("UPDATE research_run_controls SET status=?,result_json=? WHERE run_id=? AND sequence=?", ("FAILED" if failed else "DONE", json.dumps(result, ensure_ascii=False), run_id, sequence))


def build_spec(project_dir: str | Path, research_database: str | Path, *, runtime: str = "codex", token_budget: int | None = None, time_budget_seconds: int | None = None, model: str | None = None, sandbox: str = "workspace-write", reasoning_effort: str | None = None) -> RunSpec:
    project = Path(project_dir).resolve(); database = Path(research_database).resolve()
    goal_path = project / "goal.json"
    goal = json.loads(goal_path.read_text(encoding="utf-8"))
    if token_budget is not None and token_budget <= 0: raise ValueError("token_budget must be positive")
    if time_budget_seconds is not None and time_budget_seconds <= 0: raise ValueError("time_budget_seconds must be positive")
    if sandbox not in {"read-only", "workspace-write"}: raise ValueError("runner sandbox must be read-only or workspace-write")
    if reasoning_effort is not None and reasoning_effort not in EFFORT_CHOICES:
        raise ValueError("unsupported reasoning effort request")
    objective = str(goal.get("north_star") or goal.get("objective") or "").strip()
    if not objective: raise ValueError("goal.json has no approved objective")
    if len(objective) > 4000: raise ValueError("native objective exceeds 4000 characters")
    if token_budget is None and time_budget_seconds is None: raise ValueError("an explicit resource budget is required")
    return RunSpec(str(project), str(database), str(goal_path), str(goal.get("goal_id") or "approved-goal"), canonical_sha256(goal), objective, runtime, token_budget, time_budget_seconds, model, sandbox, reasoning_effort=reasoning_effort)


class ResearchRunner:
    def __init__(self, store: RuntimeStore, host: NativeHost): self.store, self.host = store, host

    @staticmethod
    def _instructions(spec: dict[str, Any]) -> str:
        return ("Own this runner-created research session. Load the approved goal and current research through the local JSON Module Interface before reasoning. "
                "The central research question is how this goal can be achieved. Develop and revise a causal explanation and an achievable strategy, not just a report. "
                f"Always pass --database {json.dumps(spec['research_database'])}; never use the default database. "
                "Codex owns scientific questions, causal synthesis, reverse-design, forward consequence tests, and cross-system inquiry. "
                "Read the local plugins/frontier-science-model/skills/goal-research/SKILL.md and follow project instructions. "
                "The human researcher can inspect results, question assumptions and steer direction during work; integrate feedback without waiting after every result. "
                "Use native parallel agents for useful independent research, sharing intermediate findings and exact receipts. "
                "If a tool or model is missing, investigate alternatives and build or connect grounded question-specific analyses, without invented biology. "
                "Retain material contributions and unfinished reasoning in the selected database. Use only the selected-database local JSON CLI for research storage, not ambient MCP servers pointing at other databases. "
                f"CLI executable: {json.dumps(spec.get('python_executable', sys.executable))}, arguments: -m frontier_research_harness.adapters.research_cli TOOL --database {json.dumps(spec['research_database'])}; send tool arguments as JSON via stdin or --input. "
                "Native goal continuation is the only continuation controller. Do not activate physical strategies or treat turn completion as goal attainment.")

    def _check_goal(self, run: dict[str, Any]) -> None:
        goal = json.loads(Path(run["spec"]["goal_path"]).read_text(encoding="utf-8"))
        if canonical_sha256(goal) != run["spec"]["goal_digest"]:
            raise RuntimeError("approved goal file changed; prepare a new explicit run instead of silently replacing the goal")

    def budget_expired(self, run: dict[str, Any]) -> bool:
        seconds, started = run["spec"].get("time_budget_seconds"), run.get("started_at")
        return bool(seconds and started and (datetime.now(timezone.utc) - datetime.fromisoformat(started)).total_seconds() >= seconds)

    def start(self, run_id: str, owner: str) -> dict[str, Any]:
        run = self.store.get(run_id); self.store.assert_owner(run_id, owner)
        if run["state"] != "PREPARED": raise RuntimeError("only a prepared run can start")
        self._check_goal(run)
        spec = run["spec"]
        execution = resolve_execution(self.host, spec)
        execution["instruction_sources"] = instruction_identity(spec["project_dir"])
        request = {"cwd": spec["project_dir"], "developerInstructions": self._instructions(spec), "sandbox": spec["sandbox"]}
        request.update(thread_overrides(execution))
        op = self.store.begin_operation(run_id, owner, "thread/start", request)
        try: response = self.host.call("thread/start", request)
        except Exception as exc:
            self.store.needs_attention(run_id, owner, f"thread/start acknowledgement uncertain: {exc}"); raise
        thread = response.get("thread", response); thread_id = thread.get("id") or response.get("threadId")
        if not thread_id:
            self.store.needs_attention(run_id, owner, "thread/start returned no thread id"); raise RuntimeError("host returned no thread id")
        execution, confirmed = observed_execution(execution, response)
        self.store.acknowledge(run_id, owner, op, response, state="THREAD_READY", managed_thread_id=thread_id, runtime_identity=self.host.runtime_identity, execution_json=execution)
        if not confirmed:
            self.store.needs_attention(run_id, owner, "Host did not confirm the requested model/effort; goal was not activated.")
            raise RuntimeError("host model/effort confirmation mismatch")
        # Paused binding loads intent before activation. Active is the sole work dispatch.
        paused = {"threadId": thread_id, "objective": spec["objective"], "status": "paused", "tokenBudget": spec.get("token_budget")}
        op = self.store.begin_operation(run_id, owner, "thread/goal/set-paused", paused)
        try: paused_response = self.host.call("thread/goal/set", paused)
        except Exception as exc:
            self.store.needs_attention(run_id, owner, f"native goal capability unavailable or acknowledgement uncertain: {exc}"); raise
        self.store.acknowledge(run_id, owner, op, paused_response, state="GOAL_BOUND", native_goal_json=paused_response.get("goal", paused_response))
        active = {"threadId": thread_id, "status": "active"}
        op = self.store.begin_operation(run_id, owner, "thread/goal/activate", active)
        try: active_response = self.host.call("thread/goal/set", active)
        except Exception as exc:
            self.store.needs_attention(run_id, owner, f"goal activation acknowledgement uncertain; do not replay: {exc}"); raise
        self.store.acknowledge(run_id, owner, op, active_response, state="RUNNING", started_at=_now(), native_goal_json=active_response.get("goal", active_response))
        self.consume(run_id, owner)
        return self.store.get(run_id)

    def consume(self, run_id: str, owner: str) -> int:
        self.store.assert_owner(run_id, owner); count = 0
        for event in self.host.drain_events():
            if self.store.record_event(run_id, owner, event): count += 1
        return count

    def status(self, run_id: str, owner: str) -> dict[str, Any]:
        run = self.store.get(run_id); self.store.assert_owner(run_id, owner)
        if run["managed_thread_id"]:
            try:
                goal_response = self.host.call("thread/goal/get", {"threadId": run["managed_thread_id"]})
                goal = goal_response.get("goal")
                with self.store.connection:
                    self.store.assert_owner(run_id, owner)
                    self.store.connection.execute("UPDATE research_runs SET native_goal_json=?,updated_at=? WHERE run_id=?", (json.dumps(goal, ensure_ascii=False) if goal else None, _now(), run_id))
            except Exception as exc:
                self.store.needs_attention(run_id, owner, f"host status reconciliation failed: {exc}")
        self.consume(run_id, owner)
        return self.store.get(run_id)

    def resume(self, run_id: str, owner: str) -> dict[str, Any]:
        run = self.store.get(run_id); self.store.assert_owner(run_id, owner)
        self._check_goal(run)
        if run["pending_operation"] or run["state"] == "NEEDS_ATTENTION":
            self.store.needs_attention(run_id, owner, run.get("attention_reason") or "saved dispatch has uncertain acknowledgement; inspect host before any replay")
            return self.store.get(run_id)
        current = self.status(run_id, owner); goal = current.get("native_goal") or {}
        if current["state"] == "NEEDS_ATTENTION": return current
        if not goal or goal.get("objective") != current["spec"]["objective"]:
            self.store.needs_attention(run_id, owner, "native goal is absent or differs from the prepared goal")
            return self.store.get(run_id)
        if self.budget_expired(current):
            return self.pause(run_id, owner)
        if goal.get("status") in NON_REACTIVATING_STATES - {"paused"}:
            return current
        if not current.get("managed_thread_id"): raise RuntimeError("run has no managed thread")
        request = {"threadId": current["managed_thread_id"]}
        execution = current.get("execution") or {"model": current["spec"].get("model"), "effort": None}
        request.update(thread_overrides(execution))
        op = self.store.begin_operation(run_id, owner, "thread/resume", request)
        try: response = self.host.call("thread/resume", request)
        except Exception as exc:
            self.store.needs_attention(run_id, owner, f"thread resume acknowledgement uncertain: {exc}"); raise
        execution, confirmed = observed_execution(execution, response)
        execution["resume_instruction_sources"] = instruction_identity(current["spec"]["project_dir"])
        self.store.acknowledge(run_id, owner, op, response, execution_json=execution)
        if not confirmed:
            # A resumed active native goal may already be working: park it before reporting.
            self.pause(run_id, owner)
            self.store.needs_attention(run_id, owner, "Host did not confirm pinned model/effort on resume; inspect before activation.")
            raise RuntimeError("host model/effort confirmation mismatch on resume")
        self.consume(run_id, owner)
        return {**self.store.get(run_id), "thread": response.get("thread", response)}

    def activate(self, run_id: str, owner: str) -> dict[str, Any]:
        """Explicit user restart of a paused goal; never reset native accounting."""
        run = self.resume(run_id, owner)
        if run["state"] == "NEEDS_ATTENTION" or run["pending_operation"]:
            raise RuntimeError("reconcile uncertain operations before activation")
        if self.budget_expired(run): raise RuntimeError("time budget exhausted; prepare a new explicitly budgeted run")
        goal = run.get("native_goal") or {}
        if goal.get("status") != "paused": raise RuntimeError("only a paused goal can be explicitly activated")
        if goal.get("tokenBudget") is not None and goal.get("tokensUsed", 0) >= goal["tokenBudget"]:
            raise RuntimeError("native token budget exhausted")
        request = {"threadId": run["managed_thread_id"], "status": "active"}
        op = self.store.begin_operation(run_id, owner, "thread/goal/activate", request)
        try: response = self.host.call("thread/goal/set", request)
        except Exception as exc:
            self.store.needs_attention(run_id, owner, f"activation acknowledgement uncertain: {exc}"); raise
        self.store.acknowledge(run_id, owner, op, response, state="RUNNING", attention_reason=None,
                               native_goal_json=response.get("goal"))
        return self.store.get(run_id)

    def recover(self, run_id: str, owner: str, *, prior_host_stopped: bool) -> dict[str, Any]:
        """Operator-confirmed recovery parks an existing goal; it never dispatches work."""
        if not prior_host_stopped: raise ValueError("confirm the prior host has stopped before recovery")
        run = self.store.get(run_id); self.store.assert_owner(run_id, owner)
        self._check_goal(run)
        if not run["managed_thread_id"]:
            raise RuntimeError("no acknowledged thread id; inspect host history, do not replay thread/start")
        status = self.host.call("thread/goal/get", {"threadId": run["managed_thread_id"]})
        goal = status.get("goal") or {}
        if goal.get("objective") != run["spec"]["objective"]:
            raise RuntimeError("native goal absent or changed; recovery cannot replace it")
        # The old operation remains explicitly uncertain in its audit record.
        with self.store.connection:
            self.store.connection.execute("UPDATE research_run_operations SET status='UNKNOWN_NO_REPLAY' WHERE run_id=? AND status='DISPATCHING'", (run_id,))
            self.store.connection.execute("UPDATE research_runs SET pending_operation_json=NULL,requests_json=NULL,active_turn_id=NULL WHERE run_id=?", (run_id,))
        if goal.get("status") not in {"active", "paused"}:
            with self.store.connection:
                self.store.connection.execute("UPDATE research_runs SET state='INACTIVE',native_goal_json=? WHERE run_id=?", (json.dumps(goal), run_id))
            return self.store.get(run_id)
        return self.pause(run_id, owner)

    def pause(self, run_id: str, owner: str) -> dict[str, Any]:
        self.consume(run_id, owner)
        run = self.store.get(run_id); self.store.assert_owner(run_id, owner); thread_id = run.get("managed_thread_id")
        if not thread_id: raise RuntimeError("run has no managed thread")
        op = self.store.begin_operation(run_id, owner, "pause", {"threadId": thread_id})
        try:
            goal_response = self.host.call("thread/goal/set", {"threadId": thread_id, "status": "paused"})
            self.consume(run_id, owner)
            turn_id = self.store.get(run_id).get("active_turn_id")
            try:
                interrupt_response = self.host.call("turn/interrupt", {"threadId": thread_id, "turnId": turn_id}) if turn_id else {}
            except HostRejected:
                # The turn may have ended after we observed it; require the end event.
                self.consume(run_id, owner)
                if self.store.get(run_id).get("active_turn_id") == turn_id: raise
                interrupt_response = {"already_ended": True}
            final_goal = self.host.call("thread/goal/get", {"threadId": thread_id})
        except Exception as exc:
            self.store.needs_attention(run_id, owner, f"pause acknowledgement ambiguous: {exc}"); raise
        if (final_goal.get("goal") or {}).get("status") != "paused":
            self.store.needs_attention(run_id, owner, "pause race: host did not confirm paused goal")
            return self.store.get(run_id)
        response = {"goal_set": goal_response, "interrupt": interrupt_response, "goal_get": final_goal}
        self.store.acknowledge(run_id, owner, op, response, state="PAUSED", active_turn_id=None,
                               requests_json={}, attention_reason=None, native_goal_json=final_goal.get("goal"))
        return self.store.get(run_id)

    def steer(self, run_id: str, owner: str, text: str) -> dict[str, Any]:
        if not text.strip(): raise ValueError("steering text cannot be empty")
        run = self.store.get(run_id); self.store.assert_owner(run_id, owner)
        if run["state"] != "RUNNING": raise RuntimeError("steering requires a running owned goal")
        if not run.get("active_turn_id"): raise RuntimeError("host has no confirmed active turn to steer")
        request = {"threadId": run["managed_thread_id"], "expectedTurnId": run["active_turn_id"], "input": [{"type": "text", "text": text}]}
        op = self.store.begin_operation(run_id, owner, "turn/steer", request)
        try: response = self.host.call("turn/steer", request)
        except HostRejected as exc:
            self.store.acknowledge(run_id, owner, op, {"rejected": str(exc)})
            raise
        except Exception as exc:
            self.store.needs_attention(run_id, owner, f"steering delivery uncertain; do not resend automatically: {exc}"); raise
        self.store.acknowledge(run_id, owner, op, response)
        return response

    def respond(self, run_id: str, owner: str, request_id: str, result: dict[str, Any]) -> dict[str, Any]:
        self.store.assert_owner(run_id, owner)
        run = self.store.get(run_id); requests = run.get("requests") or {}
        if request_id not in requests: raise ValueError("no pending host request with that id")
        if not isinstance(result, dict): raise ValueError("host response must be an object")
        op = self.store.begin_operation(run_id, owner, "host/respond", {"request_id": request_id, "result": result})
        try: self.host.respond(requests[request_id]["id"], result)
        except Exception as exc:
            self.store.needs_attention(run_id, owner, f"host response delivery uncertain: {exc}"); raise
        del requests[request_id]
        # JSON-RPC server responses have no second acknowledgement: report SENT, not approved/completed.
        sent = {"sent": True, "request_id": request_id, "host_completion_confirmed": False}
        self.store.acknowledge(run_id, owner, op, sent, requests_json=requests,
                               state="WAITING_FOR_USER" if requests else "RUNNING")
        return sent

    def process_controls(self, run_id: str, owner: str) -> bool:
        keep_running = True
        for control in self.store.pending_controls(run_id, owner):
            run = self.store.get(run_id)
            if control["kind"] == "steer" and (not run["active_turn_id"] or run["state"] != "RUNNING"):
                continue  # Queue through idle gaps; never manufacture another continuation turn.
            try:
                with self.store.connection:
                    self.store.connection.execute("UPDATE research_run_controls SET status='DISPATCHING' WHERE sequence=?", (control["sequence"],))
                if control["kind"] == "pause": result = self.pause(run_id, owner)
                elif control["kind"] == "steer":
                    from frontier_research_harness.adapters.frontier_science_workspace import FrontierScienceWorkspace
                    with FrontierScienceWorkspace(run["spec"]["research_database"]) as workspace:
                        entry = workspace.research_log("append", {"author": "USER", "text": control["payload"]["text"], "session_id": run["managed_thread_id"],
                            "label": "Human research direction; not activation approval", "references": [f"runtime-control:{run_id}:{control['sequence']}"]})
                    result = {"delivery": self.steer(run_id, owner, control["payload"]["text"]), "research_entry": entry}
                elif control["kind"] == "respond":
                    result = self.respond(run_id, owner, str(control["payload"]["request_id"]), control["payload"]["result"])
                else: result, keep_running = self.pause(run_id, owner), False
                self.store.finish_control(run_id, owner, control["sequence"], result)
            except Exception as exc:
                self.store.finish_control(run_id, owner, control["sequence"], {"error": str(exc)}, failed=True)
                if self.store.get(run_id)["state"] == "NEEDS_ATTENTION": return False
            if control["kind"] in {"pause", "stop"}: return False
        return keep_running
