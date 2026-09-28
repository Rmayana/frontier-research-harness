"""Explicit foreground control for runner-owned native Codex research goals."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from frontier_research_harness.codex_app_server import CodexAppServer, handshake
from frontier_research_harness.research_runtime import ResearchRunner, RuntimeStore, build_spec
from frontier_research_harness.research_settings import EFFORT_CHOICES


def _print(value: object) -> None: print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-database", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--project", type=Path, required=True); prepare.add_argument("--research-database", type=Path, required=True)
    prepare.add_argument("--token-budget", type=int); prepare.add_argument("--time-budget-seconds", type=int)
    prepare.add_argument("--model"); prepare.add_argument("--sandbox", choices=["read-only", "workspace-write"], default="workspace-write")
    prepare.add_argument("--reasoning-effort", choices=EFFORT_CHOICES, default="highest_supported",
                         help="Thread-local effort; highest_supported resolves against the host model catalog at start")
    for name in ("start", "resume", "activate", "status", "events", "controls", "pause", "stop", "recover"):
        sub = commands.add_parser(name); sub.add_argument("run_id")
        if name in {"events", "controls"}:
            sub.add_argument("--after", type=int, default=0)
            sub.add_argument("--limit", type=int, default=100)
        if name == "recover": sub.add_argument("--prior-host-stopped", action="store_true", required=True)
    steer = commands.add_parser("steer"); steer.add_argument("run_id"); steer.add_argument("text")
    respond = commands.add_parser("respond"); respond.add_argument("run_id")
    respond.add_argument("request_id"); respond.add_argument("--input", type=Path, required=True)
    commands.add_parser("handshake")
    args = parser.parse_args()
    if args.command == "handshake": _print(handshake()); return
    with RuntimeStore(args.runtime_database) as store:
        if args.command == "prepare":
            if args.token_budget is None and args.time_budget_seconds is None:
                parser.error("prepare requires --token-budget and/or --time-budget-seconds")
            spec = build_spec(args.project, args.research_database, token_budget=args.token_budget,
                              time_budget_seconds=args.time_budget_seconds, model=args.model, sandbox=args.sandbox,
                              reasoning_effort=args.reasoning_effort)
            _print(store.prepare(spec)); return
        if args.command == "status": _print(store.get(args.run_id)); return
        if args.command == "events": _print(store.events(args.run_id, args.after, args.limit)); return
        if args.command == "controls": _print(store.controls(args.run_id, args.after, args.limit)); return
        if args.command in {"pause", "stop"}: _print({"queued_control": store.submit_control(args.run_id, args.command)}); return
        if args.command == "steer": _print({"queued_control": store.submit_control(args.run_id, "steer", {"text": args.text})}); return
        if args.command == "respond":
            result = json.loads(args.input.read_text(encoding="utf-8"))
            if not isinstance(result, dict): parser.error("response must be a JSON object matching the pending host request")
            _print({"queued_control": store.submit_control(args.run_id, "respond", {"request_id": args.request_id, "result": result})}); return

        owner = store.acquire(args.run_id)
        try:
            with CodexAppServer() as host:
                runner = ResearchRunner(store, host)
                if args.command == "recover":
                    _print(runner.recover(args.run_id, owner, prior_host_stopped=args.prior_host_stopped)); return
                run = getattr(runner, args.command)(args.run_id, owner)
                _print(run)
                last_sequence = 0
                while True:
                    try:
                        runner.consume(args.run_id, owner)
                        for event in store.events(args.run_id, last_sequence):
                            _print(event); last_sequence = event["sequence"]
                        current = store.get(args.run_id); goal = current.get("native_goal") or {}
                        if current["state"] == "NEEDS_ATTENTION": break
                        if not runner.process_controls(args.run_id, owner): break
                        if runner.budget_expired(current):
                            runner.pause(args.run_id, owner); break
                        if goal.get("status") in {"paused", "blocked", "usageLimited", "budgetLimited", "complete"}: break
                        time.sleep(0.2)
                    except KeyboardInterrupt:
                        runner.pause(args.run_id, owner); break
        except BaseException as exc:
            store.needs_attention(args.run_id, owner, f"Controller ended with {type(exc).__name__}; inspect persisted operations before recovery.")
            raise
        finally:
            # The owned subprocess is closed before a different controller can acquire.
            store.release(args.run_id, owner)
            _print(store.get(args.run_id))


if __name__ == "__main__": main()
