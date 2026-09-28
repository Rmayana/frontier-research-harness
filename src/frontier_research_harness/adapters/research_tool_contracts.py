"""Transport-independent public research tool contracts."""
from __future__ import annotations

from typing import Any

from frontier_research_harness.footage_contracts import FootageObservation
from frontier_research_harness.research_contracts import ResearchEntry
from .scientific_knowledge import SOURCES

RESEARCH_SECTION_NAMES = [
    "recent_activity",
    "fixed_goal",
    "current_understanding",
    "current_state",
    "constraints",
    "hypotheses",
    "research_notes",
    "promising_methods",
    "goal",
    "state",
    "notes",
    "research",
    "methods",
]


def _research_statement_schema() -> dict[str, Any]:
    id_array = {
        "type": "array",
        "uniqueItems": True,
        "items": {"type": "string", "minLength": 1},
    }
    return {
        "type": "object",
        "properties": {
            "statement": {"type": "string", "minLength": 1},
            "support_status": {
                "type": "string",
                "enum": [
                    "SUPPORTED",
                    "USER_OBSERVATION",
                    "MODEL_BOUND",
                    "MEASUREMENT_DERIVED",
                    "HYPOTHESIS",
                    "INFERENCE",
                    "UNKNOWN",
                ],
            },
            "target_ids": id_array,
            "evidence_ids": id_array,
            "experiment_ids": id_array,
            "calculation_ids": id_array,
            "observation_ids": id_array,
        },
        "required": ["statement", "support_status"],
        "additionalProperties": False,
    }


def _research_update_schema() -> dict[str, Any]:
    statement_array = {
        "type": "array",
        "items": {
            "oneOf": [
                {"type": "string", "minLength": 1},
                _research_statement_schema(),
            ]
        },
    }
    return {
        "type": "object",
        "properties": {
            "fixed_goal": {"type": ["object", "null"]},
            "current_understanding": {"type": "string", "description": "Replace the current causal understanding in free text; previous versions are preserved. No prescribed outline."},
            "current_state": {"type": "object"},
            "constraints": {"type": "array"},
            "hypotheses": statement_array,
            "research_notes": statement_array,
            "promising_methods": statement_array,
        },
        "additionalProperties": False,
    }


def _personal_observation_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "observed_at": {"type": "string", "format": "date-time"},
            "target_ids": {
                "type": "array", "minItems": 1, "uniqueItems": True,
                "items": {"type": "string", "minLength": 1},
            },
            "metric": {"type": "string", "minLength": 1},
            "value": {"type": "number"},
            "unit": {"type": "string", "minLength": 1},
            "protocol": {"type": "string", "minLength": 1},
            "source_type": {
                "type": "string",
                "enum": [
                    "USER_REPORTED", "DEVICE", "LAB", "COACH_OR_RATER",
                    "IMPORTED_RECORD",
                ],
            },
            "instrument": {"type": ["string", "null"]},
            "session_id": {"type": ["string", "null"]},
            "uncertainty": {"type": ["number", "null"], "minimum": 0},
            "uncertainty_unit": {"type": ["string", "null"]},
            "context": {"type": "object"},
            "provenance": {
                "type": "array", "minItems": 1,
                "items": {"type": "object", "minProperties": 1},
            },
        },
        "required": [
            "observed_at", "target_ids", "metric", "value", "unit", "protocol",
            "source_type", "provenance",
        ],
        "additionalProperties": False,
    }


def _evidence_record_schema() -> dict[str, Any]:
    schema = {
        "type": "object",
        "properties": {
            "source": {"type": "string", "minLength": 1},
            "reference_url": {"type": "string", "minLength": 1},
            "identifier": {"type": "string"},
            "classification": {
                "type": "string",
                "enum": [
                    "EXTERNAL_RESEARCH",
                    "EXTERNAL_GUIDELINE",
                    "EXTERNAL_PRIMARY_SOURCE",
                    "USER_DOCUMENT",
                    "MODEL_DOCUMENTATION",
                ],
            },
            "title": {"type": "string", "minLength": 1},
            "content_level": {
                "type": "string",
                "enum": [
                    "record_with_abstract",
                    "full_text",
                    "guideline_text",
                    "primary_source_observation",
                    "user_document",
                    "model_documentation",
                    "structured_registry_record",
                ],
            },
            "retained_claims": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "applicability": {"type": "string", "minLength": 1},
            "limitations": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "target_ids": {
                "type": "array",
                "minItems": 1,
                "uniqueItems": True,
                "items": {"type": "string", "minLength": 1},
            },
            "evidence_passages": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "excerpt": {"type": "string", "minLength": 1, "maxLength": 1000},
                        "locator": {"type": "string", "minLength": 1},
                        "supports_claim": {"type": "string", "minLength": 1},
                    },
                    "required": ["excerpt", "locator", "supports_claim"],
                    "additionalProperties": False,
                },
            },
            "quality_appraisal": {
                "type": "object",
                "properties": {
                    "source_type": {"type": "string", "minLength": 1},
                    "population": {"type": "string", "minLength": 1},
                    "methods": {"type": "string", "minLength": 1},
                    "results": {"type": "string", "minLength": 1},
                    "directness": {
                        "type": "string",
                        "enum": ["direct", "indirect", "very_indirect", "not_applicable"],
                    },
                    "bias_or_quality_limits": {
                        "type": "array", "minItems": 1,
                        "items": {"type": "string", "minLength": 1},
                    },
                },
                "required": [
                    "source_type", "population", "methods", "results", "directness",
                    "bias_or_quality_limits",
                ],
                "additionalProperties": False,
            },
            "fetched_record": {"type": "object"},
            "source_record": {"type": "object"},
            "content_sha256": {"type": "string"},
        },
        "required": [
            "source",
            "reference_url",
            "classification",
            "title",
            "content_level",
            "retained_claims",
            "applicability",
            "limitations",
            "target_ids",
        ],
        "additionalProperties": False,
    }
    schema["properties"]["fetch_id"] = {"type": "string", "minLength": 1}
    schema["properties"]["quality_appraisal"] = {"oneOf": [
        {"type": "string", "minLength": 1, "description": "Concise source-bounded assessment in natural language."},
        schema["properties"]["quality_appraisal"],
    ]}
    schema["required"] = ["retained_claims", "applicability", "limitations", "target_ids"]
    schema["anyOf"] = [
        {"required": ["fetch_id"]},
        {"required": ["source", "reference_url", "classification", "title", "content_level"]},
    ]
    return schema




def list_tool_contracts() -> list[dict[str, Any]]:
    return [
        dict(name="read_original_record", description="Read byte-bounded pages of a retained original, or find a literal passage. Dataset reads expose the stored registration record, never the full data file. Continue using next_byte_offset and content_sha256; retrieval does not verify a claim.", inputSchema={"type": "object", "properties": {"record_type": {"type": "string", "enum": ["literature_fetch", "evidence", "experiment", "experiment_output", "understanding", "numerical_receipt", "dataset", "simulation", "simulation_chain", "projection", "comparison", "evaluation", "multirate"]}, "record_id": {"type": "string", "minLength": 1}, "byte_offset": {"type": "integer", "minimum": 0}, "max_utf8_bytes": {"type": "integer", "minimum": 1024, "maximum": 65536}, "expected_sha256": {"type": "string"}, "find_text": {"type": "string", "minLength": 1}}, "required": ["record_type", "record_id"], "additionalProperties": False}),
        dict(name="search_retained", description="Find retained originals with literal matching or full_text case-insensitive FTS5 word search. Stable chronological pages and exact reload locators; discovery is not verified evidence.", inputSchema={"type": "object", "properties": {"query": {"type": "string", "minLength": 1}, "mode": {"type": "string", "enum": ["literal", "full_text"], "default": "literal"}, "after_rowid": {"type": "integer", "minimum": 0}, "through_rowid": {"type": "integer", "minimum": 0}, "record_type": {"type": "string", "enum": ["literature_fetch", "evidence", "experiment_output", "research_entry", "numerical_receipt", "dataset"]}, "limit": {"type": "integer", "minimum": 1, "maximum": 100}}, "required": ["query", "record_type"], "additionalProperties": False}),
        dict(name="research_log", description="Append optional user/Codex contributions, interpretations or plan drafts, or page through their history. Free labels; no required questions, workflow, evidence promotion or activation.", inputSchema={"type": "object", "properties": {"operation": {"type": "string", "enum": ["append", "list"]}, "payload": {"anyOf": [ResearchEntry.model_json_schema(), {"type": "object", "properties": {"after_sequence": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": 100}}, "additionalProperties": False}]}}, "required": ["operation", "payload"], "additionalProperties": False}),
        dict(name="inspect_environment", description="Inspect configured scholarly sources, local model readiness and fallback entrypoint. Does not claim network availability or host tool exposure.", inputSchema={"type": "object", "properties": {}, "additionalProperties": False}),
        dict(name="load_research", description="Resume with the approved objective, current understanding and recent receipt locators within a byte limit. Reload exact results before interpreting them; history_limit retrieves prior understanding versions.", inputSchema={"type": "object", "properties": {"sections": {"type": "array", "items": {"type": "string", "enum": RESEARCH_SECTION_NAMES}}, "recent_items": {"type": "integer", "minimum": 1, "maximum": 200, "default": 10}, "max_utf8_bytes": {"type": "integer", "minimum": 4096, "maximum": 262144, "default": 32768}, "full_goal": {"type": "boolean", "default": False}, "history_limit": {"type": "integer", "minimum": 0, "maximum": 200, "default": 0}}}),
        dict(name="load_goal_map", description="Load the goal-map overview or a selected connected subgraph; links are research context, not causal proof.", inputSchema={"type": "object", "properties": {"target_ids": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "string", "minLength": 1}}, "benchmark_ids": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "string", "minLength": 1}}, "capacity_ids": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "string", "minLength": 1}}, "combat_task_ids": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "string", "minLength": 1}}}, "additionalProperties": False}),
        dict(name="save_research", description="Replace current_understanding with history preserved. Pass load_research.updated_at as expected_updated_at for parallel synthesis; on conflict reread and reconcile, never blindly overwrite. Strong factual labels require receipts.", inputSchema={"type": "object", "properties": {"data": _research_update_schema(), "expected_updated_at": {"type": "string"}, "fixed_goal_change_approved": {"type": "boolean", "default": False}}, "required": ["data"], "additionalProperties": False}),
        dict(name="list_knowledge_sources", description="Show configured research sources, access conditions and coverage. Configuration is not proof of access; paid usage is not activated.", inputSchema={"type": "object", "properties": {}}),
        dict(name="search_literature", description="Discover candidate literature with one simple input shape. Supply one or more queries; repeat returned next_queries to page beyond the first results. One failed query does not discard the others.", inputSchema={"type": "object", "properties": {"queries": {"type": "array", "minItems": 1, "maxItems": 40, "items": {"type": "object", "properties": {"source": {"type": "string", "enum": list(SOURCES)}, "query": {"type": "string", "minLength": 1}, "cursor": {"type": "string", "description": "Use the exact next_cursor returned by the previous page."}}, "required": ["source", "query"], "additionalProperties": False}}, "page_size": {"type": "integer", "minimum": 1, "maximum": 50, "default": 25}}, "required": ["queries"], "additionalProperties": False}),
        dict(name="fetch_literature", description="Fetch and automatically preserve a source response. Returns its content level and fetch_id for save_evidence without resending the payload. Retrieval alone is not read evidence.", inputSchema={"type": "object", "properties": {"source": {"type": "string", "enum": list(SOURCES)}, "identifier": {"type": "string"}}, "required": ["source", "identifier"]}),
        dict(name="save_evidence", description="Link claims to inspected evidence using fetch_id or an exact source payload. A fetch_id supplies source metadata automatically; provide title if absent. Scholarly claims need located passages and a free-text or structured quality appraisal. Metadata alone is rejected.", inputSchema={"type": "object", "properties": {"record": _evidence_record_schema()}, "required": ["record"]}),
        dict(name="save_footage_observation", description="Validate and preserve one timestamped primary fight or training footage observation. Repeated-pattern status and derived drills remain explicit rather than inferred.", inputSchema={"type": "object", "properties": {"observation": FootageObservation.model_json_schema()}, "required": ["observation"], "additionalProperties": False}),
        dict(name="list_footage_observations", description="List concise timestamped primary-footage observations, optionally filtered by exact athlete name.", inputSchema={"type": "object", "properties": {"athlete": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50}}, "additionalProperties": False}),
        dict(name="compare_footage_observations", description="Load two or more exact footage observations and expose shared action/context labels without inventing semantic similarity or ranking a pattern.", inputSchema={"type": "object", "properties": {"evidence_ids": {"type": "array", "minItems": 2, "uniqueItems": True, "items": {"type": "string", "minLength": 1}}}, "required": ["evidence_ids"], "additionalProperties": False}),
        dict(name="load_evidence", description="Load one retained evidence record exactly, including its saved provenance and fetched content.", inputSchema={"type": "object", "properties": {"evidence_id": {"type": "string"}}, "required": ["evidence_id"]}),
        dict(name="save_personal_observations", description="Save up to 100 immutable personal numerical observations with time, unit, protocol, uncertainty, and provenance. Invalid siblings do not discard valid observations.", inputSchema={"type": "object", "properties": {"observations": {"type": "array", "minItems": 1, "maxItems": 100, "items": _personal_observation_schema()}}, "required": ["observations"], "additionalProperties": False}),
        dict(name="list_personal_observations", description="Load recent personal observations and descriptive same-protocol series without attributing causality or predicting adaptation.", inputSchema={"type": "object", "properties": {"target_ids": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "string", "minLength": 1}}, "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50}}, "additionalProperties": False}),
    ]
