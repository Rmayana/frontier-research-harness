"""Minimal MCP surface: Codex reasons; this server stores and computes."""
from __future__ import annotations

import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from frontier_research_harness.footage_contracts import FootageObservation
from .frontier_science_workspace import FrontierScienceWorkspace


RESEARCH_SECTION_NAMES = [
    "fixed_goal",
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


def _coverage_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "scope": {"type": "string", "enum": ["whole_goal", "selected_targets"]},
            "requested_target_ids": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
            },
            "target_statuses": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "target_id": {"type": "string", "minLength": 1},
                        "status": {
                            "type": "string",
                            "enum": ["researched", "unresolved"],
                        },
                        "finding": {"type": "string", "minLength": 1},
                        "evidence_ids": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"type": "string", "minLength": 1},
                        },
                        "experiment_ids": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 1},
                        },
                        "calculation_ids": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 1},
                        },
                    },
                    "required": ["target_id", "status", "finding", "evidence_ids"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["scope", "target_statuses"],
        "additionalProperties": False,
    }


def _evidence_record_schema() -> dict[str, Any]:
    return {
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
        ],
        "additionalProperties": False,
    }


async def _list_tools(_context: Any = None, _params: Any = None) -> ListToolsResult:
    return ListToolsResult(tools=[
        Tool(name="load_research", description="Load a small, token-bounded view of the exact fixed goal, automatically available personal baseline, current state, and retained research. Canonical section names and the goal/state/research aliases are accepted.", inputSchema={"type": "object", "properties": {"sections": {"type": "array", "items": {"type": "string", "enum": RESEARCH_SECTION_NAMES}}, "recent_items": {"type": "integer", "minimum": 1, "maximum": 200, "default": 20}, "max_utf8_bytes": {"type": "integer", "minimum": 4096, "maximum": 262144, "default": 65536}, "full_goal": {"type": "boolean", "default": False}}}),
        Tool(name="save_research", description="Merge concise retained research. For a synthesis, include a one-turn coverage receipt mapping every target in scope to retained evidence and only target-compatible experiments or calculations. Physical coverage must include every relevant executable model layer; technical-footage-only scope requires primary footage but no unrelated model run. The receipt is validated but not stored as a workflow object.", inputSchema={"type": "object", "properties": {"data": {"type": "object"}, "fixed_goal_change_approved": {"type": "boolean", "default": False}, "coverage": _coverage_schema()}, "required": ["data"]}),
        Tool(name="list_knowledge_sources", description="Show the free research sources available for Codex to use automatically.", inputSchema={"type": "object", "properties": {}}),
        Tool(name="search_literature", description="Discover candidate literature with one simple input shape. Supply one or more queries; repeat returned next_queries to page beyond the first results. One failed query does not discard the others.", inputSchema={"type": "object", "properties": {"queries": {"type": "array", "minItems": 1, "maxItems": 40, "items": {"type": "object", "properties": {"source": {"type": "string", "enum": ["pubmed", "europe_pmc", "crossref", "clinical_trials", "nsca"]}, "query": {"type": "string", "minLength": 1}, "cursor": {"type": "string", "description": "Use the exact next_cursor returned by the previous page."}}, "required": ["source", "query"], "additionalProperties": False}}, "page_size": {"type": "integer", "minimum": 1, "maximum": 50, "default": 25}}, "required": ["queries"], "additionalProperties": False}),
        Tool(name="fetch_literature", description="Fetch a selected primary record or available open full text after candidate discovery. The response labels whether it is full text, a record with abstract, or metadata only.", inputSchema={"type": "object", "properties": {"source": {"type": "string", "enum": ["pubmed", "europe_pmc", "crossref", "clinical_trials", "nsca"]}, "identifier": {"type": "string"}}, "required": ["source", "identifier"]}),
        Tool(name="save_evidence", description="Preserve evidence only after it was inspected. Store the exact fetched/source payload, retained claims, applicability, limitations, and content level; metadata-only scholarly records are rejected.", inputSchema={"type": "object", "properties": {"record": _evidence_record_schema()}, "required": ["record"]}),
        Tool(name="save_footage_observation", description="Validate and preserve one timestamped primary fight or training footage observation. Repeated-pattern status and derived drills remain explicit rather than inferred.", inputSchema={"type": "object", "properties": {"observation": FootageObservation.model_json_schema()}, "required": ["observation"], "additionalProperties": False}),
        Tool(name="list_footage_observations", description="List concise timestamped primary-footage observations, optionally filtered by exact athlete name.", inputSchema={"type": "object", "properties": {"athlete": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50}}, "additionalProperties": False}),
        Tool(name="compare_footage_observations", description="Load two or more exact footage observations and expose shared action/context labels without inventing semantic similarity or ranking a pattern.", inputSchema={"type": "object", "properties": {"evidence_ids": {"type": "array", "minItems": 2, "uniqueItems": True, "items": {"type": "string", "minLength": 1}}}, "required": ["evidence_ids"], "additionalProperties": False}),
        Tool(name="load_evidence", description="Load one retained evidence record exactly, including its saved provenance and fetched content.", inputSchema={"type": "object", "properties": {"evidence_id": {"type": "string"}}, "required": ["evidence_id"]}),
        Tool(name="list_models", description="List connected external scientific models and their real execution status. Pass the physical goal targets in scope to receive deterministic relevance and required-layer routing; Codex still chooses the scientific questions and model within each layer.", inputSchema={"type": "object", "properties": {"target_ids": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "string", "minLength": 1}}}, "additionalProperties": False}),
        Tool(name="describe_model", description="Give Codex a model's input contract and outputs when needed.", inputSchema={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}),
        Tool(name="run_model", description="Run a decision-relevant external scientific-model experiment and automatically preserve its exact input, version, provenance, and raw output.", inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "input": {"type": "object"}, "question": {"type": "string", "minLength": 1}, "interpretation": {"type": "string"}, "provenance": {"type": "array", "minItems": 1, "items": {"type": "object", "minProperties": 1}}}, "required": ["name", "input", "question", "provenance"]}),
        Tool(name="load_experiment", description="Load the exact input, model version, raw output, provenance, and saved interpretation for one recorded experiment.", inputSchema={"type": "object", "properties": {"experiment_id": {"type": "string"}}, "required": ["experiment_id"]}),
        Tool(name="list_experiments", description="List saved experiments so Codex can compare or reproduce them.", inputSchema={"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50}}}),
        Tool(name="compare_runs", description="Compare two or more experiments without dumping full trajectories by default. Codex may request exact decision-relevant output paths; no winner or score is fabricated.", inputSchema={"type": "object", "properties": {"experiment_ids": {"type": "array", "minItems": 2, "items": {"type": "string"}}, "output_paths": {"type": "array", "items": {"type": "string"}}}, "required": ["experiment_ids"]}),
        Tool(name="calculate_target", description="Run a deterministic, unit-checked calculation for one of the 27 fixed physical targets. Empty inputs return the exact missing inputs. Successful calculations are immutable and explicitly do not predict biological adaptation.", inputSchema={"type": "object", "properties": {"target_id": {"type": "string", "minLength": 1}, "inputs": {"type": "object", "additionalProperties": {"oneOf": [{"type": "number"}, {"type": "array", "minItems": 1, "items": {"type": "number"}}]}}, "units": {"type": "object", "additionalProperties": {"type": "string"}}, "method": {"type": "string"}}, "required": ["target_id"], "additionalProperties": False}),
        Tool(name="calculate_targets", description="Validate and calculate a portfolio of distinct physical targets. Valid siblings are preserved when another item is missing or invalid; no biological forecast is produced.", inputSchema={"type": "object", "properties": {"requests": {"type": "array", "minItems": 1, "maxItems": 27, "items": {"type": "object", "properties": {"target_id": {"type": "string", "minLength": 1}, "inputs": {"type": "object", "additionalProperties": {"oneOf": [{"type": "number"}, {"type": "array", "minItems": 1, "items": {"type": "number"}}]}}, "units": {"type": "object", "additionalProperties": {"type": "string"}}, "method": {"type": "string"}}, "required": ["target_id"], "additionalProperties": False}}}, "required": ["requests"], "additionalProperties": False}),
        Tool(name="assess_targets", description="Project the latest immutable calculations across the 27 fixed physical targets and report target met, observed gap, or measurement required. This does not predict feasibility or adaptation.", inputSchema={"type": "object", "properties": {"target_ids": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "string", "minLength": 1}}}, "additionalProperties": False}),
        Tool(name="load_calculation", description="Load one immutable target calculation with its exact inputs, units, formula version, and result.", inputSchema={"type": "object", "properties": {"calculation_id": {"type": "string"}}, "required": ["calculation_id"], "additionalProperties": False}),
    ])


async def _call_tool(_context: Any, params: Any) -> CallToolResult:
    name = params.name
    args = params.arguments or {}
    with FrontierScienceWorkspace() as workspace:
        if name == "load_research":
            result = workspace.load_research(
                sections=args.get("sections"),
                recent_items=args.get("recent_items", 20),
                max_utf8_bytes=args.get("max_utf8_bytes", 65536),
                full_goal=args.get("full_goal", False),
            )
        elif name == "save_research":
            result = workspace.save_research(
                args["data"],
                fixed_goal_change_approved=args.get("fixed_goal_change_approved", False),
                coverage=args.get("coverage"),
            )
        elif name == "list_knowledge_sources":
            result = workspace.list_knowledge_sources()
        elif name == "search_literature":
            # Accept earlier/hallucinated names for recovery, but advertise only
            # the canonical queries/page_size shape above.
            queries = args.get("queries") or args.get("searches") or args.get("portfolio")
            if queries is None and "source" in args and "query" in args:
                queries = [{"source": args["source"], "query": args["query"], "cursor": args.get("cursor")}]
            if queries is None:
                raise ValueError(
                    'search_literature requires {"queries":[{"source":"pubmed","query":"..."}],"page_size":25}'
                )
            page_size = args.get(
                "page_size",
                args.get("limit_per_query", args.get("limit_per_search", args.get("limit", 25))),
            )
            result = workspace.search_literature_portfolio(
                queries, limit_per_search=page_size
            )
        elif name == "fetch_literature":
            result = workspace.fetch_literature(args["source"], args["identifier"])
        elif name == "save_evidence":
            result = workspace.save_evidence(args["record"])
        elif name == "save_footage_observation":
            result = workspace.save_footage_observation(args["observation"])
        elif name == "list_footage_observations":
            result = workspace.list_footage_observations(
                athlete=args.get("athlete"), limit=args.get("limit", 50)
            )
        elif name == "compare_footage_observations":
            result = workspace.compare_footage_observations(args["evidence_ids"])
        elif name == "load_evidence":
            result = workspace.load_evidence(args["evidence_id"])
        elif name == "list_models":
            result = workspace.list_models(args.get("target_ids"))
        elif name == "describe_model":
            result = workspace.describe_model(args["name"])
        elif name == "run_model":
            result = workspace.run_model(args["name"], args["input"], question=args.get("question"), interpretation=args.get("interpretation"), provenance=args.get("provenance"))
        elif name == "load_experiment":
            result = workspace.load_experiment(args["experiment_id"])
        elif name == "list_experiments":
            result = workspace.list_experiments(args.get("limit", 50))
        elif name == "compare_runs":
            result = workspace.compare_runs(
                args["experiment_ids"], output_paths=args.get("output_paths")
            )
        elif name == "calculate_target":
            result = workspace.calculate_target(
                args["target_id"],
                args.get("inputs"),
                units=args.get("units"),
                method=args.get("method"),
            )
        elif name == "calculate_targets":
            result = workspace.calculate_targets(args["requests"])
        elif name == "assess_targets":
            result = workspace.assess_targets(args.get("target_ids"))
        elif name == "load_calculation":
            result = workspace.load_calculation(args["calculation_id"])
        else:
            raise ValueError(f"unknown tool: {name}")
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, ensure_ascii=False))])


server = Server(
    "frontier-science-model",
    on_list_tools=_list_tools,
    on_call_tool=_call_tool,
)


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
