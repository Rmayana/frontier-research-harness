"""Small runtime receipt for Frontier Science Model tool execution.

This does not judge scientific claims or choose research actions. It only keeps
the agent from silently finalizing after tool errors, metadata-only discovery,
or failed persistence.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path
from typing import Any


RESEARCH_TOOLS = {
    "load_research",
    "save_research",
    "list_knowledge_sources",
    "search_literature",
    "fetch_literature",
    "save_evidence",
    "save_footage_observation",
    "list_footage_observations",
    "compare_footage_observations",
    "load_evidence",
    "list_models",
    "describe_model",
    "run_model",
    "load_experiment",
    "list_experiments",
    "compare_runs",
    "calculate_target",
    "calculate_targets",
    "assess_targets",
    "load_calculation",
}


def _tool_name(value: Any) -> str:
    name = str(value or "")
    return name.rsplit("__", 1)[-1]


def _data_directory(override: str | Path | None = None) -> Path:
    if override is not None:
        root = Path(override)
    elif os.environ.get("PLUGIN_DATA"):
        root = Path(os.environ["PLUGIN_DATA"])
    else:
        root = Path(tempfile.gettempdir()) / "frontier-science-model-hook"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _connect(data_directory: str | Path | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(
        _data_directory(data_directory) / "execution-receipts.sqlite3",
        timeout=5,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS tool_events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            turn_id TEXT NOT NULL,
            created_at REAL NOT NULL,
            tool_name TEXT NOT NULL,
            success INTEGER NOT NULL,
            details_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "DELETE FROM tool_events WHERE created_at < ?", (time.time() - 7 * 86400,)
    )
    connection.commit()
    return connection


def _response_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        content = value.get("content")
        if isinstance(content, list):
            parts = [
                str(item.get("text"))
                for item in content
                if isinstance(item, dict) and item.get("text") is not None
            ]
            if parts:
                return "\n".join(parts)
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value or "")


def _model_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        structured = value.get("structuredContent") or value.get("structured_content")
        if isinstance(structured, dict):
            return structured
    text = _response_text(value).strip()
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _failed(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("isError") is True or value.get("is_error") is True:
            return True
        if str(value.get("status") or "").casefold() in {"error", "failed"}:
            return True
    lowered = _response_text(value).casefold()
    return any(
        marker in lowered
        for marker in (
            "error executing tool",
            "tool execution failed",
            "validation error",
            '"iserror": true',
            '"is_error": true',
        )
    )


def _event_details(tool: str, tool_input: Any, tool_response: Any) -> dict[str, Any]:
    input_value = tool_input if isinstance(tool_input, dict) else {}
    payload = _model_payload(tool_response)
    details: dict[str, Any] = {"input_keys": sorted(input_value)}
    if tool == "load_research":
        details["sections"] = input_value.get("sections")
    elif tool == "search_literature":
        queries = (
            input_value.get("queries")
            or input_value.get("searches")
            or input_value.get("portfolio")
            or ([{"source": input_value.get("source"), "query": input_value.get("query")}] if input_value.get("query") else [])
        )
        details.update(
            query_count=len(queries) if isinstance(queries, list) else 0,
            candidate_count=int(payload.get("unique_result_count") or 0),
            failed_search_count=int(payload.get("failed_search_count") or 0),
        )
    elif tool == "fetch_literature":
        details.update(
            source=input_value.get("source"),
            identifier=input_value.get("identifier"),
            content_level=payload.get("content_level"),
        )
    elif tool == "save_evidence":
        record = input_value.get("record")
        record = record if isinstance(record, dict) else {}
        details.update(
            evidence_id=payload.get("evidence_id"),
            classification=record.get("classification"),
            content_level=record.get("content_level"),
            retained_claim_count=len(record.get("retained_claims", []))
            if isinstance(record.get("retained_claims"), list)
            else 0,
        )
    elif tool == "list_models":
        models = payload.get("models")
        models = models if isinstance(models, list) else []
        details["executable_model_count"] = sum(
            1 for item in models
            if isinstance(item, dict) and item.get("execution_available") is True
        )
    elif tool == "run_model":
        provenance = input_value.get("provenance")
        details.update(
            model_name=input_value.get("name"),
            experiment_id=payload.get("experiment_id"),
            model_layer=payload.get("research_layer"),
            has_question=bool(str(input_value.get("question") or "").strip()),
            provenance_count=len(provenance) if isinstance(provenance, list) else 0,
        )
    elif tool == "save_research":
        coverage = payload.get("research_coverage")
        coverage = coverage if isinstance(coverage, dict) else {}
        submitted_coverage = input_value.get("coverage")
        submitted_coverage = submitted_coverage if isinstance(submitted_coverage, dict) else {}
        submitted_statuses = submitted_coverage.get("target_statuses")
        submitted_statuses = submitted_statuses if isinstance(submitted_statuses, list) else []
        coverage_experiment_ids = sorted({
            experiment_id
            for item in submitted_statuses
            if isinstance(item, dict)
            for experiment_id in item.get("experiment_ids", [])
            if isinstance(experiment_id, str) and experiment_id
        })
        details.update(
            coverage_validated=coverage.get("validated") is True,
            coverage_scope=coverage.get("scope"),
            coverage_target_count=int(coverage.get("target_count") or 0),
            coverage_experiment_ids=coverage_experiment_ids,
            coverage_required_model_layers=coverage.get("required_model_layers", []),
            coverage_covered_model_layers=coverage.get("covered_model_layers", []),
            coverage_target_ids=sorted({
                str(item.get("target_id"))
                for item in submitted_statuses
                if isinstance(item, dict) and item.get("target_id")
            }),
        )
    return details


def _canonical_hint(tool: str) -> str:
    hints = {
        "load_research": 'Use canonical sections or aliases such as ["goal", "state", "research"].',
        "search_literature": 'Retry with {"queries":[{"source":"pubmed","query":"..."}],"page_size":25}. Use returned next_queries for later pages.',
        "save_research": "Retry with concise data and a coverage receipt that maps every target in the declared scope to retained evidence IDs.",
        "fetch_literature": 'Retry with the exact source and identifier from a search result.',
        "save_evidence": "Retry with the inspected payload, title, content level, retained claims, applicability, and limitations; metadata alone is not evidence.",
        "run_model": "Inspect the model contract, construct valid inputs, and supply a decision-relevant question plus exact provenance. If this model cannot run, choose another executable relevant model.",
    }
    return hints.get(tool, "Inspect the tool result, correct the input, and retry this tool before finalizing.")


def _record_post_tool(event: dict[str, Any], data_directory: str | Path | None) -> dict[str, Any]:
    tool = _tool_name(event.get("tool_name"))
    if tool not in RESEARCH_TOOLS:
        return {}
    success = not _failed(event.get("tool_response"))
    details = _event_details(tool, event.get("tool_input"), event.get("tool_response"))
    duplicate_fetch = False
    with closing(_connect(data_directory)) as connection:
        if (
            tool == "fetch_literature"
            and success
            and details.get("source")
            and details.get("identifier")
        ):
            earlier = connection.execute(
                "SELECT details_json FROM tool_events WHERE session_id=? AND turn_id=? AND tool_name='fetch_literature' AND success=1",
                (
                    str(event.get("session_id") or "unknown"),
                    str(event.get("turn_id") or "unknown"),
                ),
            ).fetchall()
            duplicate_fetch = any(
                (prior := json.loads(row["details_json"])).get("source") == details["source"]
                and prior.get("identifier") == details["identifier"]
                for row in earlier
            )
        connection.execute(
            "INSERT INTO tool_events(session_id,turn_id,created_at,tool_name,success,details_json) VALUES(?,?,?,?,?,?)",
            (
                str(event.get("session_id") or "unknown"),
                str(event.get("turn_id") or "unknown"),
                time.time(),
                tool,
                int(success),
                json.dumps(details, ensure_ascii=False),
            ),
        )
        connection.commit()
    if not success:
        return {
            "decision": "block",
            "reason": f"The {tool} research tool failed. {_canonical_hint(tool)}",
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "A failed research tool is unresolved; recover it instead of treating the research as complete.",
            },
        }
    if tool == "search_literature" and details.get("failed_search_count", 0):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "Some literature queries failed while others succeeded. Preserve the successful results and retry the failed query families before synthesis.",
            }
        }
    if duplicate_fetch:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "This source and identifier were already fetched in this turn. Reuse the prior record and spend the next call on an uncovered target or a different source.",
            }
        }
    return {}


def _stop_decision(event: dict[str, Any], data_directory: str | Path | None) -> dict[str, Any]:
    session_id = str(event.get("session_id") or "unknown")
    turn_id = str(event.get("turn_id") or "unknown")
    with closing(_connect(data_directory)) as connection:
        rows = connection.execute(
            "SELECT * FROM tool_events WHERE session_id=? AND turn_id=? ORDER BY sequence",
            (session_id, turn_id),
        ).fetchall()
        if not rows:
            return {}
        if event.get("stop_hook_active"):
            connection.execute(
                "DELETE FROM tool_events WHERE session_id=? AND turn_id=?",
                (session_id, turn_id),
            )
            connection.commit()
            return {}

        events = [
            {
                "tool": row["tool_name"],
                "success": bool(row["success"]),
                "details": json.loads(row["details_json"]),
            }
            for row in rows
        ]
        successful = {item["tool"] for item in events if item["success"]}
        unresolved = []
        for index, item in enumerate(events):
            if item["success"]:
                continue
            if not any(
                later["tool"] == item["tool"] and later["success"]
                for later in events[index + 1 :]
            ):
                unresolved.append(item["tool"])

        search_events = [
            item for item in events if item["tool"] == "search_literature" and item["success"]
        ]
        candidates_found = any(
            item["details"].get("candidate_count", 0) > 0 for item in search_events
        )
        partial_failure_unrecovered = any(
            item["details"].get("failed_search_count", 0) > 0 for item in search_events
        ) and not (
            search_events and search_events[-1]["details"].get("failed_search_count", 0) == 0
        )
        goal_loaded = any(
            item["tool"] == "load_research"
            and item["success"]
            and (
                item["details"].get("sections") is None
                or any(
                    name in {"fixed_goal", "goal"}
                    for name in item["details"].get("sections", [])
                )
            )
            for item in events
        )
        goal_research_activity = goal_loaded and any(
            item["success"]
            and item["tool"] in {
                "search_literature",
                "fetch_literature",
                "save_evidence",
                "run_model",
            }
            for item in events
        )
        successful_model_runs = [
            item for item in events
            if item["tool"] == "run_model"
            and item["success"]
            and item["details"].get("experiment_id")
        ]
        validated_coverage = [
            item for item in events
            if item["tool"] == "save_research"
            and item["success"]
            and item["details"].get("coverage_validated")
        ]
        current_model_runs = {
            str(item["details"]["experiment_id"]): item["details"].get("model_layer")
            for item in successful_model_runs
        }
        required_current_layers = {
            str(layer)
            for item in validated_coverage
            for layer in item["details"].get("coverage_required_model_layers", [])
            if layer
        }
        attached_current_layers = {
            str(layer)
            for item in validated_coverage
            for experiment_id in item["details"].get("coverage_experiment_ids", [])
            if (layer := current_model_runs.get(str(experiment_id)))
        }
        missing_current_layers = sorted(
            required_current_layers - attached_current_layers
        )
        technical_only_coverage = any(
            item["details"].get("coverage_target_ids") == ["technical_goal"]
            for item in validated_coverage
        )
        model_required = goal_research_activity and not technical_only_coverage

        reasons: list[str] = []
        if unresolved:
            reasons.append("retry unresolved failed tools: " + ", ".join(sorted(set(unresolved))))
        if partial_failure_unrecovered:
            reasons.append("retry the failed literature query families")
        if candidates_found and "fetch_literature" not in successful:
            reasons.append("fetch and read selected decision-relevant primary records")
        if candidates_found and "save_evidence" not in successful:
            reasons.append("save the retained evidence with exact provenance")
        if model_required and "list_models" not in successful:
            reasons.append("inspect the connected external-model catalog")
        if model_required and not successful_model_runs:
            reasons.append(
                "successfully run target-relevant external-model experiments across every required model layer; one convenient model family is not enough"
            )
        if goal_research_activity and not validated_coverage:
            reasons.append(
                "save a validated coverage receipt mapping every fixed-goal target in scope to retained evidence"
            )
        elif model_required and validated_coverage and missing_current_layers:
            reasons.append(
                "run and attach a current-turn target-compatible experiment for each missing model layer: "
                + ", ".join(missing_current_layers)
            )
        elif (search_events or successful_model_runs) and "save_research" not in successful:
            reasons.append("save concise findings, failures, and important unknowns")

        if not reasons:
            connection.execute(
                "DELETE FROM tool_events WHERE session_id=? AND turn_id=?",
                (session_id, turn_id),
            )
            connection.commit()
            return {}
        return {
            "decision": "block",
            "reason": "Research execution is incomplete. Before finalizing: " + "; ".join(reasons) + ". Do not claim completion until these checks succeed. Never fabricate model input; if one model cannot accept a valid input, select another executable model and run a decision-relevant boundary or sensitivity experiment.",
        }


def handle(event: dict[str, Any], data_directory: str | Path | None = None) -> dict[str, Any]:
    hook = event.get("hook_event_name")
    if hook == "PostToolUse":
        return _record_post_tool(event, data_directory)
    if hook == "Stop":
        return _stop_decision(event, data_directory)
    return {}


def main() -> int:
    try:
        event = json.load(sys.stdin)
        result = handle(event)
    except Exception as exc:
        # Hook bugs must remain visible but must not create a continuation loop.
        result = {"systemMessage": f"Frontier research execution receipt failed: {type(exc).__name__}: {exc}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
