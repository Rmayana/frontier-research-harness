"""Thread-local research configuration; no model calls or scientific policy."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any


EFFORT_ORDER = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")
EFFORT_CHOICES = ("inherit", "highest_supported", *EFFORT_ORDER)


def instruction_identity(project: str) -> list[dict[str, str]]:
    root = Path(project)
    skill = root / "plugins/frontier-science-model/skills/goal-research"
    files = [root / "AGENTS.md", skill / "SKILL.md", *sorted((skill / "references").glob("*.md"))]
    return [{"path": str(path.relative_to(root)), "sha256": sha256(path.read_bytes()).hexdigest()}
            for path in files if path.is_file()]


def resolve_execution(host: Any, spec: dict[str, Any]) -> dict[str, Any]:
    """Use the configured model, never substitute a supposedly smarter model."""
    requested = spec.get("reasoning_effort")
    if requested in (None, "inherit"):
        return {"requested_effort": requested, "requested_model": spec.get("model"),
                "model": spec.get("model"), "effort": None}
    if requested not in EFFORT_CHOICES:
        raise ValueError("unsupported reasoning effort request")
    model = spec.get("model")
    if not model:
        config = host.call("config/read", {"cwd": spec["project_dir"], "includeLayers": False})
        model = config.get("config", {}).get("model")
    models, cursor, seen = [], None, set()
    while True:
        params: dict[str, Any] = {"limit": 100, "includeHidden": True}
        if cursor is not None:
            params["cursor"] = cursor
        page = host.call("model/list", params)
        models.extend(page.get("data", []))
        cursor = page.get("nextCursor")
        if not cursor:
            break
        if cursor in seen:
            raise ValueError("model catalog repeated its pagination cursor")
        seen.add(cursor)
    matches = [m for m in models if model in (m.get("model"), m.get("id"))] if model else [
        m for m in models if m.get("isDefault")]
    if len(matches) != 1:
        raise ValueError("cannot unambiguously resolve the configured model in the host catalog")
    selected = matches[0]
    supported = [option["reasoningEffort"] for option in selected.get("supportedReasoningEfforts", [])]
    if requested == "highest_supported":
        if not supported or any(value not in EFFORT_ORDER for value in supported):
            raise ValueError("cannot order advertised reasoning efforts; choose a supported explicit effort")
        effort = max(supported, key=EFFORT_ORDER.index)
    else:
        effort = requested
    if effort not in supported:
        raise ValueError(f"model does not advertise requested reasoning effort: {effort}")
    return {"requested_effort": requested, "requested_model": spec.get("model"),
            "model": selected["model"], "effort": effort, "supported_efforts": supported}


def thread_overrides(execution: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if execution.get("model"):
        result["model"] = execution["model"]
    if execution.get("effort"):
        result["config"] = {"model_reasoning_effort": execution["effort"]}
    return result


def observed_execution(execution: dict[str, Any], response: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    observed = {"model": response.get("model"), "effort": response.get("reasoningEffort")}
    confirmed = all(not execution.get(key) or execution[key] == observed[key] for key in ("model", "effort"))
    result = {**execution, "observed": observed,
              "verification": "confirmed" if confirmed and execution.get("effort") else "unverified"}
    return result, confirmed
