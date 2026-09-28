"""Shared paths, constants, and pure workspace helpers."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from pydantic import BaseModel
from frontier_research_harness.scientific_contracts import canonical_sha256
from frontier_research_harness.goal_structure import load_goal_research_map, summarize_goal_research_map

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "personal" / "goal-research.sqlite3"
PERSONAL_PROFILE = PROJECT_ROOT / "data" / "personal" / "user-profile.json"
BODY_COMPOSITION_BASELINE = PROJECT_ROOT / "data" / "personal" / "inbody-2026-08-22.json"

DEFAULT_RESEARCH_SECTIONS = (
    "fixed_goal",
    "current_understanding",
    "current_state",
    "constraints",
    "hypotheses",
    "research_notes",
    "promising_methods",
)

APPEND_ONLY_SECTIONS = {
    "constraints",
    "hypotheses",
    "research_notes",
    "promising_methods",
}

TRACEABLE_RESEARCH_SECTIONS = {
    "hypotheses",
    "research_notes",
    "promising_methods",
}

SECTION_ALIASES = {
    "goal": "fixed_goal",
    "state": "current_state",
    "notes": "research_notes",
    "research": "research_notes",
    "methods": "promising_methods",
}

EVIDENCE_CLASSIFICATIONS = {
    "EXTERNAL_RESEARCH",
    "EXTERNAL_GUIDELINE",
    "EXTERNAL_PRIMARY_SOURCE",
    "USER_DOCUMENT",
    "MODEL_DOCUMENTATION",
}

EVIDENCE_CONTENT_LEVELS = {
    "record_with_abstract",
    "full_text",
    "guideline_text",
    "primary_source_observation",
    "user_document",
    "model_documentation",
    "structured_registry_record",
}

GOAL_COVERAGE_STATUSES = {"researched", "unresolved"}
TECHNICAL_GOAL_TARGET_ID = "technical_goal"

def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_tool_input(model: type[BaseModel], value: dict[str, Any]) -> BaseModel:
    """Validate JSON-shaped MCP input without rejecting JSON arrays for tuples."""
    return model.model_validate_json(json.dumps(value, ensure_ascii=False))


def _append_unique(existing: list[Any], incoming: list[Any]) -> list[Any]:
    """Append without erasing lineage or duplicating identical JSON values."""
    result = list(existing)
    seen = {canonical_sha256(_jsonable(item)) for item in result}
    for item in incoming:
        digest = canonical_sha256(_jsonable(item))
        if digest not in seen:
            result.append(item)
            seen.add(digest)
    return result


def _merge_document(current: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(current)
    for key, value in update.items():
        previous = merged.get(key)
        if key in APPEND_ONLY_SECTIONS:
            if not isinstance(value, list):
                raise ValueError(f"{key} must be a JSON array")
            if previous is not None and not isinstance(previous, list):
                raise ValueError(f"stored {key} is not a JSON array")
            merged[key] = _append_unique(previous or [], value)
        elif isinstance(previous, dict) and isinstance(value, dict):
            merged[key] = _merge_document(previous, value)
        else:
            merged[key] = value
    return merged


def _goal_summary(goal: Any) -> Any:
    if not isinstance(goal, dict):
        return goal
    if "physical_targets" in goal:
        summary = {
            "goal_id": goal.get("goal_id"),
            "revision": goal.get("revision"),
            "status": goal.get("status"),
            "north_star": goal.get("north_star"),
            "horizon": goal.get("horizon"),
            "performance_context": goal.get("performance_context"),
            "physical_goal": goal.get("physical_goal"),
            "physical_targets": goal.get("physical_targets", []),
            "measurement_benchmarks": goal.get("measurement_benchmarks", []),
            "technical_goal": goal.get("technical_goal"),
            "research_structure": goal.get("research_structure"),
            "optimization_objective": goal.get("optimization_objective"),
            "research_intent": goal.get("research_intent"),
            "research_artifacts": goal.get("research_artifacts"),
            "action_boundary": goal.get("action_boundary"),
            "full_goal_available": True,
        }
        if goal.get("research_structure"):
            structure = load_goal_research_map(goal, project_root=PROJECT_ROOT)
            summary["research_structure_summary"] = summarize_goal_research_map(structure)
        return summary
    return {**goal, "full_goal_available": True}


def _read_json_record(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"personal context file must contain a JSON object: {path.name}")
    return value


def _goal_physical_target_ids(goal: dict[str, Any]) -> set[str]:
    return {
        str(item["id"])
        for item in goal.get("physical_targets", [])
        if isinstance(item, dict) and item.get("id")
    }


def _goal_benchmark_ids(goal: dict[str, Any]) -> set[str]:
    return {
        str(item["id"])
        for item in goal.get("measurement_benchmarks", [])
        if isinstance(item, dict) and item.get("id")
    }


def _goal_target_benchmarks(goal: dict[str, Any]) -> dict[str, set[str]]:
    result = {
        str(item["id"]): {
            str(benchmark_id) for benchmark_id in item.get("benchmark_ids", [])
        }
        for item in goal.get("physical_targets", [])
        if isinstance(item, dict) and item.get("id")
    }
    for benchmark_id in _goal_benchmark_ids(goal):
        result[benchmark_id] = {benchmark_id}
    result[TECHNICAL_GOAL_TARGET_ID] = set()
    return result


def _personal_state_seed() -> dict[str, Any]:
    """Load accepted personal snapshots without inventing or averaging values."""
    seed: dict[str, Any] = {}
    profile = _read_json_record(PERSONAL_PROFILE)
    if profile is not None:
        seed["personal_profile"] = {
            **profile,
            "provenance": {"kind": "local_user_record", "path": "data/personal/user-profile.json"},
        }
    body_composition = _read_json_record(BODY_COMPOSITION_BASELINE)
    if body_composition is not None:
        seed["body_composition_baseline"] = {
            **body_composition,
            "provenance": {"kind": "local_measurement_record", "path": "data/personal/inbody-2026-08-22.json"},
        }
    return seed


def _literature_identity(source: str, item: dict[str, Any]) -> str:
    doi = str(item.get("doi") or "").strip().casefold()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    if doi:
        return f"doi:{doi}"
    pmid = str(item.get("pmid") or (item.get("id") if source in {"pubmed", "nsca"} else "")).strip()
    if pmid:
        return f"pmid:{pmid.casefold()}"
    title = " ".join(str(item.get("title") or "").casefold().split())
    published = str(item.get("published") or "")[:4]
    authors = item.get("authors")
    first_author = str(authors[0] if isinstance(authors, list) and authors else authors or "").casefold()
    if title:
        return f"work:{title}|{published}|{first_author}"
    return f"{source}:{str(item.get('id') or item.get('url') or item).casefold()}"


def _output_summary(value: Any, *, depth: int = 0) -> Any:
    """Return a bounded structural summary; never select a scientific winner."""
    if depth >= 3:
        if isinstance(value, (dict, list)):
            return {"type": type(value).__name__, "count": len(value)}
        return value
    if isinstance(value, dict):
        return {
            key: _output_summary(item, depth=depth + 1)
            for key, item in list(value.items())[:40]
        }
    if isinstance(value, list):
        if not value:
            return {"type": "list", "count": 0}
        numeric = [float(item) for item in value if isinstance(item, (int, float))]
        if len(numeric) == len(value):
            return {
                "type": "numeric_list",
                "count": len(value),
                "minimum": min(numeric),
                "maximum": max(numeric),
                "first": numeric[0],
                "last": numeric[-1],
            }
        return {
            "type": "list",
            "count": len(value),
            "first": _output_summary(value[0], depth=depth + 1),
            "last": _output_summary(value[-1], depth=depth + 1),
        }
    return value
