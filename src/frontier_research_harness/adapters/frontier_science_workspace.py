"""Thin research workspace and model toolbox for Codex.

This module deliberately contains no research planner, reviewer, gate, phase, or
state machine.  Codex owns scientific judgment.  The adapter validates model
inputs, executes passive calculations, and stores reproducible raw runs.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from pydantic import BaseModel

from frontier_research_harness.adapters.scientific_knowledge import ScientificKnowledgeClient
from frontier_research_harness.scientific_contracts import canonical_sha256
from frontier_research_harness.footage_contracts import FootageObservation
from frontier_research_harness.model_relevance import (
    MODEL_REFERENCE_EXPERIMENTS,
    candidate_targets,
    model_layer,
    relevant_models_by_layer,
    required_layers,
)
from frontier_research_harness.target_calculator import (
    CalculationStatus,
    TARGET_SPECS,
    TargetCalculationRequest,
    calculate_target as calculate_target_metric,
)
from frontier_research_harness.external_models.core_experiment_contracts import (
    CORE_STUDY_CONTRACTS,
)
from frontier_research_harness.external_models.core_output_normalizers import (
    normalize_febio,
    normalize_opensim,
    normalize_pulse,
)
from frontier_research_harness.external_models.human_gem_adapter import (
    HumanGemExperimentRequest,
    HumanGemPassiveAdapter,
)
from frontier_research_harness.external_models.mitocore_adapter import (
    MitoCoreExperimentRequest,
    MitoCorePassiveAdapter,
)
from frontier_research_harness.external_models.mitochondria_qsp_adapter import (
    MitoQspExperimentRequest,
    MitochondriaQspPassiveAdapter,
)
from frontier_research_harness.external_models.model_registry import (
    unified_model_registry,
)
from frontier_research_harness.external_models.external_engine_runner import (
    ExternalEngineJob,
    ExternalEngineRunner,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "personal" / "goal-research.sqlite3"
PERSONAL_PROFILE = PROJECT_ROOT / "data" / "personal" / "user-profile.json"
BODY_COMPOSITION_BASELINE = PROJECT_ROOT / "data" / "personal" / "inbody-2026-08-22.json"

DEFAULT_RESEARCH_SECTIONS = (
    "fixed_goal",
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
        return {
            "goal_id": goal.get("goal_id"),
            "revision": goal.get("revision"),
            "status": goal.get("status"),
            "north_star": goal.get("north_star"),
            "horizon": goal.get("horizon"),
            "performance_context": goal.get("performance_context"),
            "physical_targets": goal.get("physical_targets", []),
            "technical_goal": goal.get("technical_goal"),
            "full_goal_available": True,
        }
    return {**goal, "full_goal_available": True}


def _read_json_record(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"personal context file must contain a JSON object: {path.name}")
    return value


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


class FrontierScienceWorkspace:
    """Persistence and passive model execution without workflow governance."""

    def __init__(self, database: str | Path = DEFAULT_DATABASE) -> None:
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database)
        self.connection.row_factory = sqlite3.Row
        self._ensure_schema()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "FrontierScienceWorkspace":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _ensure_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS frontier_science_workspace (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                document_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS frontier_science_experiments (
                experiment_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                question TEXT,
                model_name TEXT NOT NULL,
                model_version TEXT NOT NULL,
                input_hash TEXT NOT NULL,
                input_json TEXT NOT NULL,
                output_json TEXT NOT NULL,
                interpretation TEXT,
                provenance_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS frontier_science_evidence (
                evidence_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                source TEXT NOT NULL,
                identifier TEXT,
                reference_url TEXT NOT NULL,
                classification TEXT NOT NULL,
                record_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS frontier_science_calculations (
                calculation_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                target_id TEXT NOT NULL,
                formula_id TEXT NOT NULL,
                formula_version TEXT NOT NULL,
                input_hash TEXT NOT NULL,
                input_json TEXT NOT NULL,
                output_json TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def _bootstrap_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "fixed_goal": None,
            "current_state": {},
            "constraints": [],
            "hypotheses": [],
            "research_notes": [],
            "promising_methods": [],
        }
        goal_path = PROJECT_ROOT / "goal.json"
        if goal_path.exists():
            document["fixed_goal"] = json.loads(goal_path.read_text(encoding="utf-8"))
        document["current_state"].update(_personal_state_seed())
        return document

    def _synchronize_personal_context(self, document: dict[str, Any]) -> bool:
        current_state = document.setdefault("current_state", {})
        if not isinstance(current_state, dict):
            raise ValueError("stored current_state is not a JSON object")
        changed = False
        for key, value in _personal_state_seed().items():
            if current_state.get(key) != value:
                current_state[key] = value
                changed = True
        return changed

    def _load_document(self) -> tuple[dict[str, Any], str]:
        row = self.connection.execute(
            "SELECT document_json, updated_at FROM frontier_science_workspace WHERE singleton=1"
        ).fetchone()
        if row is None:
            document = self._bootstrap_document()
            updated_at = _utc_now()
            self.connection.execute(
                "INSERT INTO frontier_science_workspace(singleton,document_json,updated_at) VALUES(1,?,?)",
                (json.dumps(document, ensure_ascii=False), updated_at),
            )
            self.connection.commit()
        else:
            document = json.loads(row["document_json"])
            updated_at = row["updated_at"]
            if self._synchronize_personal_context(document):
                updated_at = _utc_now()
                self.connection.execute(
                    "UPDATE frontier_science_workspace SET document_json=?,updated_at=? WHERE singleton=1",
                    (json.dumps(document, ensure_ascii=False), updated_at),
                )
                self.connection.commit()
        return document, updated_at

    def load_research(
        self,
        *,
        sections: list[str] | None = None,
        recent_items: int = 20,
        max_utf8_bytes: int = 65536,
        full_goal: bool = False,
    ) -> dict[str, Any]:
        if recent_items < 1 or recent_items > 200:
            raise ValueError("recent_items must be between 1 and 200")
        if max_utf8_bytes < 4096 or max_utf8_bytes > 262144:
            raise ValueError("max_utf8_bytes must be between 4096 and 262144")
        document, updated_at = self._load_document()
        requested = [SECTION_ALIASES.get(name, name) for name in (sections or DEFAULT_RESEARCH_SECTIONS)]
        requested = list(dict.fromkeys(requested))
        unknown = sorted(set(requested) - set(document))
        if unknown:
            raise ValueError(f"unknown research sections: {', '.join(unknown)}")

        selected: dict[str, Any] = {}
        omitted: list[str] = []
        # Leave room for metadata so the tool response remains bounded.
        section_budget = max_utf8_bytes - 2048
        for name in requested:
            value = document[name]
            if name == "fixed_goal" and not full_goal:
                value = _goal_summary(value)
            elif isinstance(value, list):
                value = value[-recent_items:]
            candidate = {**selected, name: value}
            if len(json.dumps(candidate, ensure_ascii=False).encode("utf-8")) <= section_budget:
                selected[name] = value
            else:
                omitted.append(name)
        return {
            "workspace": selected,
            "updated_at": updated_at,
            "available_sections": sorted(document),
            "item_counts": {
                key: len(value)
                for key, value in document.items()
                if isinstance(value, list)
            },
            "omitted_sections": omitted,
            "context_limited": bool(omitted),
            "experiment_count": self.connection.execute(
                "SELECT COUNT(*) FROM frontier_science_experiments"
            ).fetchone()[0],
            "evidence_count": self.connection.execute(
                "SELECT COUNT(*) FROM frontier_science_evidence"
            ).fetchone()[0],
            "calculation_count": self.connection.execute(
                "SELECT COUNT(*) FROM frontier_science_calculations"
            ).fetchone()[0],
        }

    def _normalize_research_update(self, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValueError("research update must be a JSON object")
        normalized = _jsonable(data)
        unknown = sorted(set(normalized) - set(DEFAULT_RESEARCH_SECTIONS))
        if unknown:
            raise ValueError(f"unknown research sections: {', '.join(unknown)}")
        for section in APPEND_ONLY_SECTIONS & normalized.keys():
            if not isinstance(normalized[section], list):
                raise ValueError(f"{section} must be a JSON array")
        return normalized

    def save_research(
        self,
        data: dict[str, Any],
        *,
        fixed_goal_change_approved: bool = False,
        coverage: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current, _ = self._load_document()
        normalized = self._normalize_research_update(data)
        if (
            "fixed_goal" in normalized
            and current.get("fixed_goal") is not None
            and normalized["fixed_goal"] != current["fixed_goal"]
            and not fixed_goal_change_approved
        ):
            raise ValueError("changing the fixed goal requires explicit user approval")
        coverage_summary = (
            self._validate_goal_coverage(current.get("fixed_goal"), coverage)
            if coverage is not None
            else None
        )
        merged = _merge_document(current, normalized)
        updated_at = _utc_now()
        self.connection.execute(
            "UPDATE frontier_science_workspace SET document_json=?,updated_at=? WHERE singleton=1",
            (json.dumps(merged, ensure_ascii=False), updated_at),
        )
        self.connection.commit()
        response = {
            "saved": True,
            "updated_at": updated_at,
            "updated_sections": sorted(normalized),
            "item_counts": {
                key: len(merged[key])
                for key in sorted(normalized)
                if isinstance(merged.get(key), list)
            },
            "merge_policy": "maps merge recursively; research lists append with exact deduplication",
        }
        if coverage_summary is not None:
            response["research_coverage"] = coverage_summary
        return response

    def _validate_goal_coverage(
        self,
        goal: Any,
        coverage: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate a one-turn receipt without storing a workflow object."""
        if not isinstance(goal, dict):
            raise ValueError("research coverage requires a structured fixed goal")
        if not isinstance(coverage, dict):
            raise ValueError("research coverage must be a JSON object")

        scope = coverage.get("scope")
        if scope not in {"whole_goal", "selected_targets"}:
            raise ValueError("research coverage scope must be whole_goal or selected_targets")
        statuses = coverage.get("target_statuses")
        if not isinstance(statuses, list) or not statuses:
            raise ValueError("research coverage requires non-empty target_statuses")

        goal_target_ids = {
            str(item.get("id"))
            for item in goal.get("physical_targets", [])
            if isinstance(item, dict) and item.get("id")
        }
        if goal.get("technical_goal"):
            goal_target_ids.add(TECHNICAL_GOAL_TARGET_ID)
        if not goal_target_ids:
            raise ValueError("fixed goal exposes no research target IDs")

        requested_target_ids = coverage.get("requested_target_ids")
        if scope == "whole_goal":
            expected_target_ids = goal_target_ids
            if requested_target_ids not in (None, []):
                supplied = set(requested_target_ids)
                if supplied != expected_target_ids:
                    raise ValueError("whole_goal requested_target_ids must match every fixed-goal target")
        else:
            if not isinstance(requested_target_ids, list) or not requested_target_ids:
                raise ValueError("selected_targets coverage requires requested_target_ids")
            expected_target_ids = {str(item) for item in requested_target_ids}
            unknown_requested = sorted(expected_target_ids - goal_target_ids)
            if unknown_requested:
                raise ValueError(
                    "unknown requested goal target IDs: " + ", ".join(unknown_requested)
                )

        seen: set[str] = set()
        referenced_evidence: set[str] = set()
        referenced_experiments: set[str] = set()
        referenced_calculations: set[str] = set()
        technical_evidence: set[str] = set()
        experiments_by_target: dict[str, list[str]] = {}
        for index, item in enumerate(statuses):
            if not isinstance(item, dict):
                raise ValueError(f"target_statuses[{index}] must be a JSON object")
            target_id = str(item.get("target_id") or "").strip()
            if not target_id:
                raise ValueError(f"target_statuses[{index}] requires target_id")
            if target_id in seen:
                raise ValueError(f"duplicate research target status: {target_id}")
            seen.add(target_id)
            if target_id not in expected_target_ids:
                raise ValueError(f"research target is outside the declared scope: {target_id}")
            if item.get("status") not in GOAL_COVERAGE_STATUSES:
                raise ValueError(
                    f"{target_id} status must be researched or unresolved"
                )
            finding = item.get("finding")
            if not isinstance(finding, str) or not finding.strip():
                raise ValueError(f"{target_id} requires a concise finding")
            evidence_ids = item.get("evidence_ids")
            if not isinstance(evidence_ids, list) or not evidence_ids:
                raise ValueError(f"{target_id} requires at least one retained evidence_id")
            if any(not isinstance(value, str) or not value.strip() for value in evidence_ids):
                raise ValueError(f"{target_id} evidence_ids must be non-empty strings")
            experiment_ids = item.get("experiment_ids", [])
            if not isinstance(experiment_ids, list) or any(
                not isinstance(value, str) or not value.strip()
                for value in experiment_ids
            ):
                raise ValueError(f"{target_id} experiment_ids must be an array of strings")
            calculation_ids = item.get("calculation_ids", [])
            if not isinstance(calculation_ids, list) or any(
                not isinstance(value, str) or not value.strip()
                for value in calculation_ids
            ):
                raise ValueError(f"{target_id} calculation_ids must be an array of strings")
            referenced_evidence.update(evidence_ids)
            referenced_experiments.update(experiment_ids)
            referenced_calculations.update(calculation_ids)
            experiments_by_target[target_id] = list(experiment_ids)
            if target_id == TECHNICAL_GOAL_TARGET_ID:
                technical_evidence.update(evidence_ids)

        missing_targets = sorted(expected_target_ids - seen)
        if missing_targets:
            raise ValueError(
                "research coverage omitted goal targets: " + ", ".join(missing_targets)
            )

        evidence_rows = self.connection.execute(
            "SELECT evidence_id,classification,record_json FROM frontier_science_evidence"
        ).fetchall()
        evidence_by_id = {
            str(row["evidence_id"]): str(row["classification"])
            for row in evidence_rows
        }
        evidence_record_by_id = {
            str(row["evidence_id"]): json.loads(row["record_json"])
            for row in evidence_rows
        }
        unknown_evidence = sorted(referenced_evidence - set(evidence_by_id))
        if unknown_evidence:
            raise ValueError(
                "research coverage references unknown evidence IDs: "
                + ", ".join(unknown_evidence)
            )
        unusable_evidence = []
        for evidence_id in sorted(referenced_evidence):
            record = evidence_record_by_id[evidence_id]
            payload = record.get("fetched_record") or record.get("source_record")
            reusable = (
                isinstance(record.get("title"), str)
                and bool(record["title"].strip())
                and record.get("content_level") in EVIDENCE_CONTENT_LEVELS
                and isinstance(record.get("retained_claims"), list)
                and bool(record["retained_claims"])
                and isinstance(record.get("applicability"), str)
                and bool(record["applicability"].strip())
                and isinstance(record.get("limitations"), list)
                and bool(record["limitations"])
                and isinstance(payload, dict)
                and bool(payload)
                and isinstance(record.get("content_sha256"), str)
                and len(record["content_sha256"]) == 64
            )
            if not reusable:
                unusable_evidence.append(evidence_id)
        if unusable_evidence:
            raise ValueError(
                "research coverage references legacy or incomplete evidence; refetch and retain reusable read evidence: "
                + ", ".join(unusable_evidence)
            )
        technical_only_scope = expected_target_ids == {TECHNICAL_GOAL_TARGET_ID}
        required_model_layers = {
            layer.value
            for layer in required_layers(
                expected_target_ids,
                available_model_ids=self._available_model_ids(),
            )
        }
        if required_model_layers and not referenced_experiments and not technical_only_scope:
            raise ValueError(
                "research coverage must attach target-compatible external-model experiments"
            )
        experiment_rows = self.connection.execute(
            "SELECT experiment_id,question,model_name,provenance_json FROM frontier_science_experiments"
        ).fetchall()
        experiment_by_id = {
            str(row["experiment_id"]): row
            for row in experiment_rows
        }
        unknown_experiments = sorted(referenced_experiments - set(experiment_by_id))
        if unknown_experiments:
            raise ValueError(
                "research coverage references unknown experiment IDs: "
                + ", ".join(unknown_experiments)
            )
        untraceable_experiments = []
        for experiment_id in sorted(referenced_experiments):
            row = experiment_by_id[experiment_id]
            provenance = json.loads(row["provenance_json"])
            if (
                not isinstance(row["question"], str)
                or not row["question"].strip()
                or not isinstance(provenance, list)
                or not provenance
            ):
                untraceable_experiments.append(experiment_id)
        if untraceable_experiments:
            raise ValueError(
                "research coverage references experiments without a question and provenance: "
                + ", ".join(untraceable_experiments)
            )
        mismatched_experiments = []
        covered_model_layers: set[str] = set()
        covered_model_names: set[str] = set()
        for target_id, experiment_ids in experiments_by_target.items():
            for experiment_id in experiment_ids:
                row = experiment_by_id[experiment_id]
                model_name = str(row["model_name"])
                if target_id not in candidate_targets(model_name):
                    mismatched_experiments.append(
                        f"{experiment_id} ({model_name} -> {target_id})"
                    )
                    continue
                layer = model_layer(model_name)
                if layer is not None:
                    covered_model_layers.add(layer.value)
                    covered_model_names.add(model_name)
        if mismatched_experiments:
            raise ValueError(
                "external-model experiments must be attached only to compatible goal targets: "
                + ", ".join(sorted(mismatched_experiments))
            )
        missing_model_layers = sorted(required_model_layers - covered_model_layers)
        if missing_model_layers:
            raise ValueError(
                "research coverage is missing decision-relevant external-model layers: "
                + ", ".join(missing_model_layers)
            )
        if referenced_calculations:
            calculation_rows = self.connection.execute(
                "SELECT calculation_id,target_id FROM frontier_science_calculations"
            ).fetchall()
            calculation_targets = {
                str(row["calculation_id"]): str(row["target_id"])
                for row in calculation_rows
            }
            unknown_calculations = sorted(
                referenced_calculations - set(calculation_targets)
            )
            if unknown_calculations:
                raise ValueError(
                    "research coverage references unknown calculation IDs: "
                    + ", ".join(unknown_calculations)
                )
            mismatched_calculations = sorted({
                calculation_id
                for item in statuses
                if isinstance(item, dict)
                for calculation_id in item.get("calculation_ids", [])
                if calculation_targets.get(calculation_id) != str(item.get("target_id"))
            })
            if mismatched_calculations:
                raise ValueError(
                    "calculation IDs must be attached to their own physical target: "
                    + ", ".join(mismatched_calculations)
                )
        if TECHNICAL_GOAL_TARGET_ID in expected_target_ids and not any(
            evidence_by_id.get(evidence_id) == "EXTERNAL_PRIMARY_SOURCE"
            for evidence_id in technical_evidence
        ):
            raise ValueError(
                "technical_goal requires retained EXTERNAL_PRIMARY_SOURCE evidence"
            )

        return {
            "validated": True,
            "scope": scope,
            "goal_id": goal.get("goal_id"),
            "target_count": len(seen),
            "evidence_count": len(referenced_evidence),
            "experiment_count": len(referenced_experiments),
            "experiment_model_count": len(covered_model_names),
            "required_model_layers": sorted(required_model_layers),
            "covered_model_layers": sorted(covered_model_layers),
            "calculation_count": len(referenced_calculations),
            "status_counts": {
                status: sum(1 for item in statuses if item.get("status") == status)
                for status in sorted(GOAL_COVERAGE_STATUSES)
            },
        }

    def list_knowledge_sources(self) -> dict[str, Any]:
        return ScientificKnowledgeClient().list_sources()

    def search_literature(
        self,
        source: str,
        query: str,
        limit: int = 10,
        *,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return ScientificKnowledgeClient().search(source, query, limit, cursor=cursor)

    def search_literature_portfolio(
        self,
        searches: list[dict[str, Any]],
        *,
        limit_per_search: int = 10,
    ) -> dict[str, Any]:
        if not 1 <= len(searches) <= 40:
            raise ValueError("queries must contain between 1 and 40 searches")
        client = ScientificKnowledgeClient()
        responses = []
        combined: list[dict[str, Any]] = []
        seen: set[str] = set()
        next_queries: list[dict[str, Any]] = []
        failed_searches = 0
        for index, search in enumerate(searches):
            source = search.get("source")
            query = search.get("query")
            if not isinstance(source, str) or not isinstance(query, str):
                raise ValueError("each portfolio search requires source and query strings")
            cursor = search.get("cursor")
            if cursor is not None and not isinstance(cursor, str):
                raise ValueError("query cursor must be a string")
            try:
                response = client.search(source, query, limit_per_search, cursor=cursor)
            except Exception as exc:
                failed_searches += 1
                responses.append({
                    "ok": False,
                    "source": source,
                    "query": query,
                    "cursor": cursor,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                })
                continue
            response = {"ok": True, **response}
            responses.append(response)
            if response.get("next_cursor"):
                next_queries.append({
                    "source": source,
                    "query": query,
                    "cursor": response["next_cursor"],
                })
            for item in response.get("results", []):
                identity = _literature_identity(source, item)
                if identity in seen:
                    continue
                seen.add(identity)
                combined.append({"search_index": index, "source": source, **item})
        return {
            "searches": responses,
            "combined_results": combined,
            "attempted_search_count": len(searches),
            "completed_search_count": len(searches) - failed_searches,
            "failed_search_count": failed_searches,
            "returned_candidate_count": sum(
                int(response.get("returned_count", len(response.get("results", []))))
                for response in responses
                if response.get("ok")
            ),
            "unique_result_count": len(combined),
            "next_queries": next_queries,
            "more_available": bool(next_queries),
            "selection_owner": "Codex",
            "note": "Search discovers candidates. Follow next_queries for more pages, then fetch and read decision-relevant primary records before synthesis.",
        }

    def fetch_literature(self, source: str, identifier: str) -> dict[str, Any]:
        return ScientificKnowledgeClient().fetch(source, identifier)

    def save_evidence(self, record: dict[str, Any]) -> dict[str, Any]:
        required = {
            "source",
            "reference_url",
            "classification",
            "title",
            "content_level",
            "retained_claims",
            "applicability",
            "limitations",
        }
        missing = sorted(required - record.keys())
        if missing:
            raise ValueError(f"evidence record missing: {', '.join(missing)}")
        if record["classification"] not in EVIDENCE_CLASSIFICATIONS:
            raise ValueError(f"unsupported evidence classification: {record['classification']}")
        for key in ("source", "reference_url", "title", "applicability"):
            if not isinstance(record[key], str) or not record[key].strip():
                raise ValueError(f"evidence {key} must be a non-empty string")
        if record["content_level"] not in EVIDENCE_CONTENT_LEVELS:
            raise ValueError(
                "unsupported evidence content_level: " + str(record["content_level"])
            )
        for key in ("retained_claims", "limitations"):
            values = record[key]
            if not isinstance(values, list) or not values or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise ValueError(f"evidence {key} must be a non-empty array of strings")
        payload_key = (
            "fetched_record"
            if isinstance(record.get("fetched_record"), dict)
            else "source_record"
            if isinstance(record.get("source_record"), dict)
            else None
        )
        if payload_key is None or not record[payload_key]:
            raise ValueError(
                "evidence requires the exact fetched_record or inspected source_record payload"
            )
        if record["classification"] in {"EXTERNAL_RESEARCH", "EXTERNAL_GUIDELINE"}:
            if payload_key != "fetched_record":
                raise ValueError(
                    "scholarly evidence requires the exact fetched_record payload"
                )
            fetched_level = record[payload_key].get("content_level")
            if fetched_level != record["content_level"]:
                raise ValueError(
                    "evidence content_level must match fetched_record.content_level"
                )
            if fetched_level not in {"record_with_abstract", "full_text", "guideline_text"}:
                raise ValueError("metadata-only scholarly records cannot be retained as read evidence")
        if record["classification"] == "EXTERNAL_PRIMARY_SOURCE":
            if payload_key != "source_record" or record["content_level"] != "primary_source_observation":
                raise ValueError(
                    "external primary sources require a primary_source_observation source_record"
                )
        normalized_record = _jsonable(record)
        content_hash = canonical_sha256(normalized_record[payload_key])
        supplied_hash = normalized_record.get("content_sha256")
        if supplied_hash is not None and supplied_hash != content_hash:
            raise ValueError("evidence content_sha256 does not match the retained payload")
        normalized_record["content_sha256"] = content_hash
        existing = self.connection.execute(
            """
            SELECT evidence_id,created_at,record_json FROM frontier_science_evidence
            WHERE reference_url=? OR (identifier IS NOT NULL AND source=? AND identifier=?)
            ORDER BY created_at DESC LIMIT 1
            """,
            (record["reference_url"], record["source"], record.get("identifier")),
        ).fetchone()
        if (
            existing is not None
            and canonical_sha256(json.loads(existing["record_json"]))
            == canonical_sha256(normalized_record)
        ):
            return {
                "saved": True,
                "deduplicated": True,
                "evidence_id": existing["evidence_id"],
                "created_at": existing["created_at"],
            }
        evidence_id = str(uuid4())
        created_at = _utc_now()
        self.connection.execute(
            "INSERT INTO frontier_science_evidence(evidence_id,created_at,source,identifier,reference_url,classification,record_json) VALUES(?,?,?,?,?,?,?)",
            (
                evidence_id,
                created_at,
                record["source"],
                record.get("identifier"),
                record["reference_url"],
                record["classification"],
                json.dumps(normalized_record, ensure_ascii=False),
            ),
        )
        self.connection.commit()
        return {"saved": True, "deduplicated": False, "evidence_id": evidence_id, "created_at": created_at}

    def save_footage_observation(self, observation: dict[str, Any]) -> dict[str, Any]:
        validated = _validate_tool_input(FootageObservation, observation)
        saved = self.save_evidence(validated.evidence_record())
        return {
            **saved,
            "content_level": "primary_source_observation",
            "technical_goal_target_id": TECHNICAL_GOAL_TARGET_ID,
        }

    def list_footage_observations(self, *, athlete: str | None = None, limit: int = 50) -> dict[str, Any]:
        if limit < 1 or limit > 500:
            raise ValueError("footage observation limit must be between 1 and 500")
        rows = self.connection.execute(
            """
            SELECT evidence_id,created_at,record_json FROM frontier_science_evidence
            WHERE classification='EXTERNAL_PRIMARY_SOURCE'
            ORDER BY created_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        observations = []
        for row in rows:
            record = json.loads(row["record_json"])
            if record.get("content_level") != "primary_source_observation":
                continue
            source_record = record.get("source_record", {})
            if athlete and str(source_record.get("athlete", "")).casefold() != athlete.strip().casefold():
                continue
            observations.append({
                "evidence_id": row["evidence_id"], "created_at": row["created_at"],
                "title": record.get("title"), "reference_url": record.get("reference_url"),
                "athlete": source_record.get("athlete"),
                "opponent_or_context": source_record.get("opponent_or_context"),
                "start_seconds": source_record.get("start_seconds"),
                "end_seconds": source_record.get("end_seconds"),
                "observed_actions": source_record.get("observed_actions", []),
                "situational_conditions": source_record.get("situational_conditions", []),
                "repeated_pattern": source_record.get("repeated_pattern"),
            })
        return {"observations": observations, "count": len(observations)}

    def compare_footage_observations(self, evidence_ids: list[str]) -> dict[str, Any]:
        if not isinstance(evidence_ids, list) or len(evidence_ids) < 2:
            raise ValueError("compare_footage_observations requires at least two evidence IDs")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("footage evidence IDs must be unique")
        observations = []
        for evidence_id in evidence_ids:
            loaded = self.load_evidence(evidence_id)
            record = loaded["record"]
            if (
                loaded["classification"] != "EXTERNAL_PRIMARY_SOURCE"
                or record.get("content_level") != "primary_source_observation"
            ):
                raise ValueError(f"evidence is not a primary footage observation: {evidence_id}")
            observations.append({"evidence_id": evidence_id, **record["source_record"]})
        action_sets = [set(item["observed_actions"]) for item in observations]
        condition_sets = [set(item["situational_conditions"]) for item in observations]
        shared_actions = sorted(set.intersection(*action_sets))
        shared_conditions = sorted(set.intersection(*condition_sets))
        return {
            "observations": observations,
            "shared_actions_exact": shared_actions,
            "shared_conditions_exact": shared_conditions,
            "all_marked_repeated_pattern": all(item.get("repeated_pattern") is True for item in observations),
            "comparison_boundary": (
                "Exact retained labels only; Codex must judge semantic similarity, opponent-specific variation, and drill implications."
            ),
        }

    def load_evidence(self, evidence_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM frontier_science_evidence WHERE evidence_id=?",
            (evidence_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown evidence: {evidence_id}")
        return {
            "evidence_id": row["evidence_id"],
            "created_at": row["created_at"],
            "source": row["source"],
            "identifier": row["identifier"],
            "reference_url": row["reference_url"],
            "classification": row["classification"],
            "record": json.loads(row["record_json"]),
        }

    @staticmethod
    def _catalog() -> dict[str, dict[str, Any]]:
        return {
            "human_gem": {
                "version": "2.0.0",
                "available": True,
                "purpose": "Pinned Human-GEM steady-state metabolic flux experiments.",
                "time_scale": "steady state",
                "input_schema": HumanGemExperimentRequest.model_json_schema(),
                "outputs": "Objective and requested reaction fluxes for baseline and candidates.",
                "validation": "Published genome-scale model; not a personalized dynamic physiology forecast.",
                "limitations": ["Caller supplies bounds and objective", "No training adaptation or efficacy judgment"],
            },
            "mitocore": {
                "version": "1.01",
                "available": True,
                "purpose": "Pinned curated mitochondrial steady-state flux experiments.",
                "time_scale": "steady state",
                "input_schema": MitoCoreExperimentRequest.model_json_schema(),
                "outputs": "Objective and requested mitochondrial reaction fluxes.",
                "validation": "Reference metabolic network; not a whole-person model.",
                "limitations": ["Caller supplies bounds and objective", "No longitudinal training adaptation"],
            },
            "mitochondria_qsp": {
                "version": "git:e7513d3dca20673bfee0bfebaff41132009593e5",
                "available": True,
                "purpose": "Pinned mechanistic myocardial mitochondrial OXPHOS and substrate-metabolism simulation.",
                "time_scale": "seconds",
                "input_schema": MitoQspExperimentRequest.model_json_schema(),
                "outputs": "Requested state trajectories and baseline deltas.",
                "validation": "Mechanistic tissue model; not calibrated to this person.",
                "limitations": ["Myocardial context only", "Requires explicit state indices and workload"],
            },
            "registered_external_engine": {
                "version": "registered-engine-bridge-v1",
                "available": True,
                "purpose": "Execute one hash-pinned READY external runtime with engine-specific arguments and artifacts.",
                "time_scale": "engine-specific",
                "input_schema": ExternalEngineJob.model_json_schema(),
                "outputs": "Exit code, bounded stdout/stderr, and SHA-256 receipts for every declared input and output artifact.",
                "validation": "Execution and provenance bridge only; scientific validity remains model- and experiment-specific.",
                "limitations": [
                    "Caller must use describe_model and the engine's own documentation to construct valid inputs",
                    "A READY runtime is not automatically calibrated or validated for personal prediction",
                    "Only files inside this workspace may be used or declared as outputs",
                ],
            },
        }

    def assess_targets(self, target_ids: list[str] | None = None) -> dict[str, Any]:
        """Return measurement readiness from immutable calculations.

        This is a live projection, not a persisted plan or efficacy judgment.
        """
        known = self._known_goal_target_ids() - {TECHNICAL_GOAL_TARGET_ID}
        requested = known if target_ids is None else {str(item).strip() for item in target_ids}
        unknown = sorted(requested - known)
        if unknown:
            raise ValueError("unknown physical target IDs: " + ", ".join(unknown))
        rows = self.connection.execute(
            """
            SELECT c.* FROM frontier_science_calculations c
            JOIN (
              SELECT target_id, MAX(created_at) AS created_at
              FROM frontier_science_calculations GROUP BY target_id
            ) latest ON latest.target_id=c.target_id AND latest.created_at=c.created_at
            """
        ).fetchall()
        latest = {str(row["target_id"]): row for row in rows}
        targets = []
        for target_id in TARGET_SPECS:
            if target_id not in requested:
                continue
            spec = TARGET_SPECS[target_id]
            row = latest.get(target_id)
            if row is None:
                targets.append({
                    "target_id": target_id, "status": "MEASUREMENT_REQUIRED",
                    "target": spec.target, "required_inputs": list(spec.required),
                    "latest_calculation_id": None, "meets_target_floor": None,
                })
                continue
            output = json.loads(row["output_json"])
            targets.append({
                "target_id": target_id, "status": (
                    "TARGET_MET" if output.get("meets_target_floor") is True else "GAP_OBSERVED"
                ),
                "target": spec.target, "required_inputs": list(spec.required),
                "latest_calculation_id": row["calculation_id"],
                "created_at": row["created_at"], "value": output.get("value"),
                "unit": output.get("unit"),
                "meets_target_floor": output.get("meets_target_floor"),
            })
        counts = {
            status: sum(item["status"] == status for item in targets)
            for status in ("TARGET_MET", "GAP_OBSERVED", "MEASUREMENT_REQUIRED")
        }
        return {
            "targets": targets, "counts": counts, "target_count": len(targets),
            "interpretation_boundary": (
                "Latest immutable measurements only; no feasibility, adaptation, or strategy prediction."
            ),
        }

    def _available_model_ids(self) -> set[str]:
        catalog = self._catalog()
        available = {
            name for name, item in catalog.items()
            if item["available"] and model_layer(name) is not None
        }
        available.update(
            item.model_id
            for item in unified_model_registry(PROJECT_ROOT).records
            if item.runtime_status.value == "READY" and model_layer(item.model_id) is not None
        )
        return available

    @staticmethod
    def _known_goal_target_ids() -> set[str]:
        goal = _read_json_record(PROJECT_ROOT / "goal.json") or {}
        result = {
            str(item["id"])
            for item in goal.get("physical_targets", [])
            if isinstance(item, dict) and item.get("id")
        }
        if goal.get("technical_goal"):
            result.add(TECHNICAL_GOAL_TARGET_ID)
        return result

    def list_models(self, target_ids: list[str] | None = None) -> dict[str, Any]:
        requested_targets: set[str] | None = None
        if target_ids is not None:
            if not isinstance(target_ids, list) or not target_ids or any(
                not isinstance(item, str) or not item.strip() for item in target_ids
            ):
                raise ValueError("target_ids must be a non-empty array of goal target IDs")
            requested_targets = {item.strip() for item in target_ids}
            unknown = sorted(requested_targets - self._known_goal_target_ids())
            if unknown:
                raise ValueError("unknown goal target IDs: " + ", ".join(unknown))
        catalog = self._catalog()
        external = unified_model_registry(PROJECT_ROOT)
        active_names = set(catalog)
        available_model_ids = self._available_model_ids()

        def routing_metadata(name: str) -> dict[str, Any]:
            candidates = candidate_targets(name)
            return {
                "research_layer": (
                    model_layer(name).value if model_layer(name) is not None else None
                ),
                "candidate_target_ids": list(candidates),
                "target_relevant_for_current_question": (
                    bool(requested_targets.intersection(candidates))
                    if requested_targets is not None else False
                ),
            }

        models = [
                {
                    "name": name,
                    "version": item["version"],
                    "execution_available": item["available"],
                    "connection_status": "DIRECTLY_EXECUTABLE",
                    "research_readiness": (
                        "GENERIC_RUNTIME_ONLY"
                        if name == "registered_external_engine"
                        else "RESEARCH_CALLABLE"
                    ),
                    **routing_metadata(name),
                    "personalized": False,
                    "purpose": item["purpose"],
                }
                for name, item in catalog.items()
            ] + [
                {
                    "name": item.model_id,
                    "version": item.version,
                    "execution_available": item.runtime_status.value == "READY",
                    "execution_via": (
                        item.model_id
                        if item.runtime_status.value == "READY"
                        else None
                    ),
                    "connection_status": item.runtime_status.value,
                    "research_readiness": (
                        "REFERENCE_RUN_VERIFIED"
                        if item.runtime_status.value in {"READY", "MODEL_ASSET_READY"}
                        else "NOT_EXECUTABLE"
                    ),
                    **routing_metadata(item.model_id),
                    "personalized": False,
                    "purpose": item.name,
                    "blockers": list(item.blockers),
                }
                for item in external.records
                if item.model_id not in active_names
            ]
        response = {
            "models": models,
            "selection_owner": "Codex",
            "status_note": (
                "Execution availability is technical only. REFERENCE_RUN_VERIFIED means a smoke/reference case ran; "
                "it does not mean the model is target-relevant, personalized, or predictive."
            ),
        }
        if requested_targets is not None:
            response.update(
                requested_target_ids=sorted(requested_targets),
                required_model_layers=[
                    layer.value for layer in required_layers(
                        requested_targets, available_model_ids=available_model_ids
                    )
                ],
                relevant_models_by_layer=relevant_models_by_layer(
                    requested_targets, available_model_ids=available_model_ids
                ),
            )
        return response

    def describe_model(self, name: str) -> dict[str, Any]:
        active = self._catalog().get(name)
        if active is not None:
            payload = {
                "name": name,
                "execution_available": True,
                "connection_status": "DIRECTLY_EXECUTABLE",
                "research_readiness": (
                    "GENERIC_RUNTIME_ONLY"
                    if name == "registered_external_engine"
                    else "RESEARCH_CALLABLE"
                ),
                "research_layer": model_layer(name).value if model_layer(name) else None,
                "candidate_target_ids": list(candidate_targets(name)),
                "target_relevant_for_current_question": False,
                "personalized": False,
                "input_schema": active["input_schema"],
                "outputs": active["outputs"],
                "validation": active.get("validation"),
                "limitations": active.get("limitations", []),
            }
            contract = CORE_STUDY_CONTRACTS.get(name)
            if contract is not None:
                payload["research_input_schema"] = contract.model_json_schema()
                payload["research_input_boundary"] = (
                    "Typed study inputs validate files and calibration labels; Codex still owns the question and interpretation."
                )
            return payload
        try:
            record = unified_model_registry(PROJECT_ROOT).get(name)
        except KeyError as exc:
            raise ValueError(f"unknown model: {name}") from exc
        payload: dict[str, Any] = {
            "name": name,
            "execution_available": False,
            "connection_status": record.runtime_status.value,
            "inputs": list(record.requires),
            "outputs": list(record.produces),
            "research_readiness": (
                "REFERENCE_RUN_VERIFIED"
                if record.runtime_status.value in {"READY", "MODEL_ASSET_READY"}
                else "NOT_EXECUTABLE"
            ),
            "research_layer": model_layer(name).value if model_layer(name) else None,
            "candidate_target_ids": list(candidate_targets(name)),
            "target_relevant_for_current_question": False,
            "personalized": False,
            "validation_status": record.validation_status,
        }
        if record.runtime_status.value == "READY":
            payload["execution_available"] = True
            schema = ExternalEngineJob.model_json_schema()
            schema.get("properties", {}).pop("component_id", None)
            required = schema.get("required", [])
            schema["required"] = [item for item in required if item != "component_id"]
            payload["input_schema"] = schema
            contract = CORE_STUDY_CONTRACTS.get(name)
            if contract is not None:
                payload["research_readiness"] = "TYPED_STUDY_CALLABLE"
                payload["research_input_schema"] = contract.model_json_schema()
                payload["research_input_boundary"] = (
                    "The calibration label and workspace artifacts are validated; scientific interpretation remains with Codex."
                )
            payload["execution_via"] = f"run_model(name='{record.model_id}', input={{...}})"
            if name in MODEL_REFERENCE_EXPERIMENTS:
                payload["reference_experiment"] = MODEL_REFERENCE_EXPERIMENTS[name]
        elif record.blockers:
            payload["reason"] = record.blockers[0]
        return payload

    def _execute(self, name: str, model_input: dict[str, Any]) -> tuple[str, Any]:
        if name == "human_gem":
            request = _validate_tool_input(HumanGemExperimentRequest, model_input)
            return "2.0.0", HumanGemPassiveAdapter().run(request)
        if name == "mitocore":
            request = _validate_tool_input(MitoCoreExperimentRequest, model_input)
            return "1.01", MitoCorePassiveAdapter().run(request)
        if name == "mitochondria_qsp":
            request = _validate_tool_input(MitoQspExperimentRequest, model_input)
            return "git:e7513d3dca20673bfee0bfebaff41132009593e5", MitochondriaQspPassiveAdapter().run(request)
        if name == "registered_external_engine":
            request = _validate_tool_input(ExternalEngineJob, model_input)
            return "registered-engine-bridge-v1", ExternalEngineRunner().run(
                request, workspace_root=PROJECT_ROOT
            )
        try:
            external = unified_model_registry(PROJECT_ROOT).get(name)
        except KeyError:
            external = None
        if external is not None and external.runtime_status.value == "READY":
            contract = CORE_STUDY_CONTRACTS.get(name)
            if contract is not None and "study_type" in model_input:
                study = _validate_tool_input(contract, model_input)
                receipt = ExternalEngineRunner().run(study.to_job(), workspace_root=PROJECT_ROOT)
                normalized = (
                    normalize_opensim(receipt) if name == "opensim" else
                    normalize_pulse(
                        receipt,
                        exercise_end_seconds=getattr(study, "exercise_end_seconds", None),
                        recovery_interval_seconds=getattr(study, "recovery_interval_seconds", 60.0),
                    ) if name == "pulse" else
                    normalize_febio(receipt)
                )
                return external.version, {
                    "engine_receipt": receipt,
                    "normalized_observables": normalized,
                    "calibration": study.calibration.value,
                    "interpretation_status": "CODEX_OWNS_INTERPRETATION",
                }
            if "component_id" in model_input:
                raise ValueError("component_id is selected by the run_model name and must be omitted")
            request = _validate_tool_input(
                ExternalEngineJob, {"component_id": name, **model_input}
            )
            return external.version, ExternalEngineRunner().run(
                request, workspace_root=PROJECT_ROOT
            )
        raise ValueError(f"unknown or unavailable model: {name}")

    def run_model(
        self,
        name: str,
        model_input: dict[str, Any],
        *,
        question: str | None = None,
        interpretation: str | None = None,
        provenance: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("run_model requires a non-empty decision-relevant question")
        if not isinstance(provenance, list) or not provenance:
            raise ValueError("run_model requires non-empty experiment provenance")
        if any(not isinstance(item, dict) or not item for item in provenance):
            raise ValueError("run_model provenance entries must be non-empty JSON objects")
        version, raw = self._execute(name, model_input)
        raw_output = _jsonable(raw)
        experiment_id = str(uuid4())
        created_at = _utc_now()
        input_hash = canonical_sha256(model_input)
        self.connection.execute(
            """
            INSERT INTO frontier_science_experiments(
              experiment_id,created_at,question,model_name,model_version,input_hash,
              input_json,output_json,interpretation,provenance_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                experiment_id,
                created_at,
                question,
                name,
                version,
                input_hash,
                json.dumps(_jsonable(model_input), ensure_ascii=False),
                json.dumps(raw_output, ensure_ascii=False),
                interpretation,
                json.dumps(provenance or [], ensure_ascii=False),
            ),
        )
        self.connection.commit()
        return {
            "experiment_id": experiment_id,
            "created_at": created_at,
            "model_name": name,
            "model_version": version,
            "research_layer": model_layer(name).value if model_layer(name) else None,
            "candidate_target_ids": list(candidate_targets(name)),
            "input_hash": input_hash,
            "raw_output": raw_output,
            "interpretation_status": "CODEX_OWNS_INTERPRETATION",
        }

    def load_experiment(self, experiment_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM frontier_science_experiments WHERE experiment_id=?",
            (experiment_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown experiment: {experiment_id}")
        return {
            "experiment_id": row["experiment_id"],
            "created_at": row["created_at"],
            "question": row["question"],
            "model_name": row["model_name"],
            "model_version": row["model_version"],
            "research_layer": (
                model_layer(row["model_name"]).value
                if model_layer(row["model_name"]) else None
            ),
            "candidate_target_ids": list(candidate_targets(row["model_name"])),
            "input_hash": row["input_hash"],
            "input": json.loads(row["input_json"]),
            "raw_output": json.loads(row["output_json"]),
            "interpretation": row["interpretation"],
            "provenance": json.loads(row["provenance_json"]),
        }

    def list_experiments(self, limit: int = 50) -> dict[str, Any]:
        rows = self.connection.execute(
            """
            SELECT experiment_id,created_at,question,model_name,model_version,input_hash
            FROM frontier_science_experiments ORDER BY created_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        experiments = []
        for row in rows:
            item = dict(row)
            layer = model_layer(item["model_name"])
            item["research_layer"] = layer.value if layer else None
            item["candidate_target_ids"] = list(candidate_targets(item["model_name"]))
            experiments.append(item)
        return {"experiments": experiments, "count": len(experiments)}

    def calculate_target(
        self,
        target_id: str,
        inputs: dict[str, Any] | None = None,
        *,
        units: dict[str, str] | None = None,
        method: str | None = None,
    ) -> dict[str, Any]:
        """Calculate one fixed physical metric and preserve successful arithmetic."""
        request = _validate_tool_input(TargetCalculationRequest, {
            "target_id": target_id,
            "inputs": inputs or {},
            "units": units or {},
            "method": method,
        })
        result = calculate_target_metric(request)
        payload = result.model_dump(mode="json")
        if result.status is CalculationStatus.INPUT_REQUIRED:
            return {**payload, "calculation_id": None, "persisted": False}
        calculation_id = str(uuid4())
        created_at = _utc_now()
        self.connection.execute(
            """
            INSERT INTO frontier_science_calculations(
              calculation_id,created_at,target_id,formula_id,formula_version,
              input_hash,input_json,output_json
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                calculation_id,
                created_at,
                result.target_id,
                result.formula_id,
                result.formula_version,
                result.input_hash,
                json.dumps(request.model_dump(mode="json"), ensure_ascii=False),
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        self.connection.commit()
        return {
            **payload,
            "calculation_id": calculation_id,
            "created_at": created_at,
            "persisted": True,
        }

    def calculate_targets(self, requests: list[dict[str, Any]]) -> dict[str, Any]:
        """Validate a measurement portfolio without losing valid siblings."""
        if not isinstance(requests, list) or not requests:
            raise ValueError("calculate_targets requires a non-empty request array")
        if len(requests) > len(TARGET_SPECS):
            raise ValueError(f"calculate_targets accepts at most {len(TARGET_SPECS)} requests")
        seen: set[str] = set()
        results: list[dict[str, Any]] = []
        for index, request in enumerate(requests):
            if not isinstance(request, dict):
                results.append({"index": index, "status": "INVALID", "error": "request must be an object"})
                continue
            target_id = str(request.get("target_id", "")).strip()
            if target_id in seen:
                results.append({"index": index, "target_id": target_id, "status": "INVALID", "error": "duplicate target_id"})
                continue
            seen.add(target_id)
            try:
                result = self.calculate_target(
                    target_id, request.get("inputs"), units=request.get("units"),
                    method=request.get("method"),
                )
            except (TypeError, ValueError) as exc:
                results.append({"index": index, "target_id": target_id or None, "status": "INVALID", "error": str(exc)})
            else:
                results.append({"index": index, **result})
        counts = {
            status: sum(item.get("status") == status for item in results)
            for status in ("CALCULATED", "INPUT_REQUIRED", "INVALID")
        }
        return {"results": results, "counts": counts, "request_count": len(requests)}

    def load_calculation(self, calculation_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM frontier_science_calculations WHERE calculation_id=?",
            (calculation_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown calculation: {calculation_id}")
        return {
            "calculation_id": row["calculation_id"],
            "created_at": row["created_at"],
            "target_id": row["target_id"],
            "formula_id": row["formula_id"],
            "formula_version": row["formula_version"],
            "input_hash": row["input_hash"],
            "input": json.loads(row["input_json"]),
            "output": json.loads(row["output_json"]),
        }

    @staticmethod
    def _extract_output_path(raw_output: Any, path: str) -> Any:
        current = raw_output
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
                current = current[int(part)]
            else:
                raise ValueError(f"unknown output path: {path}")
        return current

    def compare_runs(
        self,
        experiment_ids: list[str],
        *,
        output_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        if len(experiment_ids) < 2:
            raise ValueError("compare_runs requires at least two experiment IDs")
        runs = []
        for experiment_id in experiment_ids:
            full = self.load_experiment(experiment_id)
            raw_output = full.pop("raw_output")
            model_input = full.pop("input")
            full["input_summary"] = _output_summary(model_input)
            full["output"] = (
                {
                    path: self._extract_output_path(raw_output, path)
                    for path in output_paths
                }
                if output_paths
                else _output_summary(raw_output)
            )
            full["output_mode"] = "SELECTED_PATHS" if output_paths else "STRUCTURAL_SUMMARY"
            runs.append(full)
        return {
            "runs": runs,
            "comparison_owner": "Codex",
            "note": (
                "No winner or scientific judgment is added. Use output_paths for exact "
                "decision-relevant values or load_experiment for one complete raw record."
            ),
        }


__all__ = ["DEFAULT_DATABASE", "FrontierScienceWorkspace"]
