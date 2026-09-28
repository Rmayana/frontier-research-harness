"""Transport-independent execution through the workspace Module Interface."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .frontier_science_workspace import FrontierScienceWorkspace


ToolArguments = dict[str, Any]
ToolResult = dict[str, Any]
ToolHandler = Callable[[FrontierScienceWorkspace, ToolArguments], ToolResult]


def tool_result_is_error(result: ToolResult) -> bool:
    statuses = {"FAILED", "PARTIAL_FAILURE", "DEPENDENCY_UNAVAILABLE"}
    nested = result.get("result")
    return result.get("status") in statuses or (isinstance(nested, dict) and nested.get("status") in statuses)


def _load_research(workspace: FrontierScienceWorkspace, args: ToolArguments) -> ToolResult:
    return workspace.load_research(
        sections=args.get("sections"),
        recent_items=args.get("recent_items", 10),
        max_utf8_bytes=args.get("max_utf8_bytes", 32768),
        full_goal=args.get("full_goal", False),
        history_limit=args.get("history_limit", 0),
    )


def _load_goal_map(workspace: FrontierScienceWorkspace, args: ToolArguments) -> ToolResult:
    return workspace.load_goal_map(
        target_ids=args.get("target_ids"),
        benchmark_ids=args.get("benchmark_ids"),
        capacity_ids=args.get("capacity_ids"),
        combat_task_ids=args.get("combat_task_ids"),
    )


def _save_research(workspace: FrontierScienceWorkspace, args: ToolArguments) -> ToolResult:
    return workspace.save_research(
        args["data"],
        fixed_goal_change_approved=args.get("fixed_goal_change_approved", False),
        expected_updated_at=args.get("expected_updated_at"),
    )


def _search_literature(workspace: FrontierScienceWorkspace, args: ToolArguments) -> ToolResult:
    """Normalize legacy search shapes while advertising only the canonical shape."""
    queries = args.get("queries") or args.get("searches") or args.get("portfolio")
    if queries is None and "source" in args and "query" in args:
        queries = [{
            "source": args["source"],
            "query": args["query"],
            "cursor": args.get("cursor"),
        }]
    if queries is None:
        raise ValueError(
            'search_literature requires {"queries":[{"source":"pubmed",'
            '"query":"..."}],"page_size":25}'
        )
    page_size = args.get(
        "page_size",
        args.get("limit_per_query", args.get("limit_per_search", args.get("limit", 25))),
    )
    return workspace.search_literature_portfolio(queries, limit_per_search=page_size)


def _list_footage_observations(
    workspace: FrontierScienceWorkspace, args: ToolArguments
) -> ToolResult:
    return workspace.list_footage_observations(
        athlete=args.get("athlete"), limit=args.get("limit", 50)
    )


def _list_personal_observations(
    workspace: FrontierScienceWorkspace, args: ToolArguments
) -> ToolResult:
    return workspace.list_personal_observations(
        target_ids=args.get("target_ids"), limit=args.get("limit", 50)
    )


_TOOL_HANDLERS: dict[str, ToolHandler] = {
    "research_log": lambda workspace, args: workspace.research_log(
        args["operation"], args["payload"]
    ),
    "read_original_record": lambda workspace, args: workspace.read_original_record(**args),
    "search_retained": lambda workspace, args: workspace.search_retained(**args),
    "inspect_environment": lambda workspace, _args: workspace.inspect_environment(),
    "load_research": _load_research,
    "load_goal_map": _load_goal_map,
    "save_research": _save_research,
    "list_knowledge_sources": lambda workspace, _args: workspace.list_knowledge_sources(),
    "search_literature": _search_literature,
    "fetch_literature": lambda workspace, args: workspace.fetch_literature(
        args["source"], args["identifier"]
    ),
    "save_evidence": lambda workspace, args: workspace.save_evidence(args["record"]),
    "save_footage_observation": lambda workspace, args: workspace.save_footage_observation(
        args["observation"]
    ),
    "list_footage_observations": _list_footage_observations,
    "compare_footage_observations": lambda workspace, args: workspace.compare_footage_observations(
        args["evidence_ids"]
    ),
    "load_evidence": lambda workspace, args: workspace.load_evidence(args["evidence_id"]),
    "save_personal_observations": lambda workspace, args: workspace.save_personal_observations(
        args["observations"]
    ),
    "list_personal_observations": _list_personal_observations,
}


def registered_research_tools() -> tuple[str, ...]:
    """Return the stable dispatch surface for contract consistency checks."""
    return tuple(_TOOL_HANDLERS)


def dispatch_research_tool(
    name: str,
    args: ToolArguments | None = None,
    *,
    database: Any = None,
) -> ToolResult:
    try:
        handler = _TOOL_HANDLERS[name]
    except KeyError:
        raise ValueError(f"unknown tool: {name}") from None

    workspace_context = (
        FrontierScienceWorkspace()
        if database is None
        else FrontierScienceWorkspace(database)
    )
    with workspace_context as workspace:
        return handler(workspace, args or {})


__all__ = [
    "dispatch_research_tool",
    "registered_research_tools",
    "tool_result_is_error",
]
