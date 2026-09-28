"""Validated linked views over the fixed whole-person goal.

The map is passive research-routing context.  It does not add success
conditions, assert causal effects, choose a strategy, or activate an
intervention.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


TargetRole = Literal[
    "performance_endpoint",
    "constraint",
    "sustainability_floor",
    "diagnostic_control",
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NamedSource(_StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    source: str = Field(min_length=1)


class CombatTask(_StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    capacity_ids: tuple[str, ...] = Field(min_length=1)
    technical_elements: tuple[str, ...] = Field(min_length=1)


class CapacityNode(_StrictModel):
    id: str = Field(min_length=1)
    success_target_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    target_ids: tuple[str, ...] = Field(min_length=1)


class TargetRoleAssignment(_StrictModel):
    primary_role: TargetRole
    secondary_roles: tuple[TargetRole, ...] = ()

    @model_validator(mode="after")
    def roles_are_distinct(self) -> "TargetRoleAssignment":
        if self.primary_role in self.secondary_roles:
            raise ValueError("primary_role cannot also be a secondary role")
        if len(self.secondary_roles) != len(set(self.secondary_roles)):
            raise ValueError("secondary_roles must be unique")
        return self


class DiagnosticNode(_StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    examples: tuple[str, ...] = Field(min_length=1)
    capacity_ids: tuple[str, ...] = Field(min_length=1)


class InterventionNode(_StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    examples: tuple[str, ...] = Field(min_length=1)
    capacity_ids: tuple[str, ...] = Field(min_length=1)
    approval_required_before_activation: Literal[True]


class ObservationSemantics(_StrictModel):
    construct_name: str = Field(alias="construct", min_length=1)
    test_task: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    instrument: str = Field(min_length=1)
    rules: tuple[str, ...] = Field(min_length=1)


class TargetObservation(_StrictModel):
    construct_name: str = Field(alias="construct", min_length=1)
    test_task: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    instrument: str = Field(min_length=1)
    protocol_status: str = Field(min_length=1)


class GoalResearchMap(_StrictModel):
    schema_version: Literal[2]
    structure_id: str = Field(min_length=1)
    goal_id: str = Field(min_length=1)
    kind: Literal["linked_maps"]
    relationship_status: Literal["RESEARCH_ROUTING_HYPOTHESES"]
    boundaries: tuple[str, ...] = Field(min_length=1)
    whole_person_views: tuple[NamedSource, ...] = Field(min_length=1)
    goal_constraints: tuple[NamedSource, ...] = Field(min_length=1)
    combat_tasks: tuple[CombatTask, ...] = Field(min_length=1)
    capacity_nodes: tuple[CapacityNode, ...] = Field(min_length=1)
    target_role_assignments: dict[str, TargetRoleAssignment]
    diagnostic_nodes: tuple[DiagnosticNode, ...] = Field(min_length=1)
    intervention_nodes: tuple[InterventionNode, ...] = Field(min_length=1)
    observation_semantics: ObservationSemantics
    target_observations: dict[str, TargetObservation]

    @model_validator(mode="after")
    def internal_links_are_valid(self) -> "GoalResearchMap":
        collections = {
            "whole_person_views": self.whole_person_views,
            "goal_constraints": self.goal_constraints,
            "combat_tasks": self.combat_tasks,
            "capacity_nodes": self.capacity_nodes,
            "diagnostic_nodes": self.diagnostic_nodes,
            "intervention_nodes": self.intervention_nodes,
        }
        for label, nodes in collections.items():
            ids = [node.id for node in nodes]
            if len(ids) != len(set(ids)):
                raise ValueError(f"{label} IDs must be unique")

        capacity_ids = {node.id for node in self.capacity_nodes}
        for node in (*self.combat_tasks, *self.diagnostic_nodes, *self.intervention_nodes):
            unknown = sorted(set(node.capacity_ids) - capacity_ids)
            if unknown:
                raise ValueError(
                    f"{node.id} references unknown capacity IDs: {', '.join(unknown)}"
                )
            if len(node.capacity_ids) != len(set(node.capacity_ids)):
                raise ValueError(f"{node.id} capacity_ids must be unique")
        for node in self.capacity_nodes:
            if len(node.target_ids) != len(set(node.target_ids)):
                raise ValueError(f"{node.id} target_ids must be unique")
        return self


def _fixed_physical_target_ids(goal: dict[str, Any]) -> set[str]:
    targets = {
        str(item["id"])
        for item in goal.get("physical_targets", [])
        if isinstance(item, dict) and item.get("id")
    }
    if len(targets) != len(goal.get("physical_targets", [])):
        raise ValueError("fixed physical targets must have unique non-empty IDs")
    return targets


def _fixed_benchmark_ids(goal: dict[str, Any]) -> set[str]:
    benchmarks = {
        str(item["id"])
        for item in goal.get("measurement_benchmarks", [])
        if isinstance(item, dict) and item.get("id")
    }
    if len(benchmarks) != len(goal.get("measurement_benchmarks", [])):
        raise ValueError("measurement benchmarks must have unique non-empty IDs")
    return benchmarks


def validate_detailed_goal(goal: dict[str, Any]) -> dict[str, Any]:
    """Validate the user-approved detailed success-condition hierarchy."""
    if goal.get("schema_version") != 2 or goal.get("revision") != 3:
        raise ValueError("detailed goal requires schema_version=2 and revision=3")
    physical_goal = goal.get("physical_goal")
    if not isinstance(physical_goal, dict):
        raise ValueError("detailed goal requires physical_goal")
    physical_targets = goal.get("physical_targets")
    if not isinstance(physical_targets, list) or not physical_targets:
        raise ValueError("detailed goal requires physical_targets")
    target_ids = _fixed_physical_target_ids(goal)
    benchmark_ids = _fixed_benchmark_ids(goal)
    component_ids: set[str] = set()
    mapped_benchmarks: set[str] = set()
    transfer_task_ids: set[str] = set()
    for target in physical_targets:
        target_id = str(target.get("id") or "")
        for field in ("name", "role", "objective", "success_condition"):
            if not isinstance(target.get(field), str) or not target[field].strip():
                raise ValueError(f"{target_id} requires {field}")
        components = target.get("functional_components")
        if not isinstance(components, list) or not components:
            raise ValueError(f"{target_id} requires functional_components")
        for component in components:
            if not isinstance(component, dict) or any(
                not isinstance(component.get(field), str) or not component[field].strip()
                for field in ("id", "name", "target")
            ):
                raise ValueError(f"{target_id} has an incomplete functional component")
            component_id = str(component["id"])
            if component_id in component_ids:
                raise ValueError(f"duplicate functional component ID: {component_id}")
            component_ids.add(component_id)
        target_benchmarks = {str(item) for item in target.get("benchmark_ids", [])}
        unknown_benchmarks = sorted(target_benchmarks - benchmark_ids)
        if unknown_benchmarks:
            raise ValueError(
                f"{target_id} references unknown quantitative subtargets: "
                + ", ".join(unknown_benchmarks)
            )
        mapped_benchmarks.update(target_benchmarks)
        transfer_task_ids.update(str(item) for item in target.get("transfer_task_ids", []))
    if mapped_benchmarks != benchmark_ids:
        raise ValueError("every quantitative subtarget must map to a physical success target")

    combat_tasks = physical_goal.get("combat_task_outcomes")
    if not isinstance(combat_tasks, list) or not combat_tasks:
        raise ValueError("detailed goal requires combat_task_outcomes")
    combat_task_ids = {
        str(item.get("id"))
        for item in combat_tasks
        if isinstance(item, dict) and item.get("id")
    }
    if len(combat_task_ids) != len(combat_tasks):
        raise ValueError("combat task IDs must be unique and non-empty")
    for task in combat_tasks:
        task_id = str(task["id"])
        if not isinstance(task.get("success_condition"), str) or not task["success_condition"].strip():
            raise ValueError(f"{task_id} requires success_condition")
        unknown_targets = sorted(
            {str(item) for item in task.get("linked_physical_target_ids", [])} - target_ids
        )
        if unknown_targets:
            raise ValueError(
                f"{task_id} references unknown physical success targets: "
                + ", ".join(unknown_targets)
            )
    if transfer_task_ids != combat_task_ids:
        raise ValueError("physical target transfer links must cover every combat task")

    context = goal.get("performance_context") or {}
    expected_counts = {
        "physical_target_count": len(target_ids),
        "combat_task_count": len(combat_task_ids),
        "functional_component_count": len(component_ids),
        "quantitative_subtarget_count": len(benchmark_ids),
    }
    for key, expected in expected_counts.items():
        if context.get(key) != expected:
            raise ValueError(f"performance_context.{key} must be {expected}")
    return {
        "validated": True,
        **expected_counts,
        "physical_target_ids": sorted(target_ids),
        "combat_task_ids": sorted(combat_task_ids),
    }


def validate_goal_research_map(
    goal: dict[str, Any], structure: GoalResearchMap
) -> dict[str, Any]:
    """Fail closed when the passive map drifts from the fixed goal."""
    detailed = validate_detailed_goal(goal)
    if structure.goal_id != goal.get("goal_id"):
        raise ValueError("goal map goal_id does not match the fixed goal")
    target_ids = _fixed_physical_target_ids(goal)
    mapped_success_target_ids = {
        capacity.success_target_id for capacity in structure.capacity_nodes
    }
    if mapped_success_target_ids != target_ids:
        missing = sorted(target_ids - mapped_success_target_ids)
        unknown = sorted(mapped_success_target_ids - target_ids)
        raise ValueError(
            "capacity success targets do not match fixed physical targets: "
            f"missing={','.join(missing)}; unknown={','.join(unknown)}"
        )
    benchmark_ids = _fixed_benchmark_ids(goal)
    structure_task_ids = {task.id for task in structure.combat_tasks}
    if structure_task_ids != set(detailed["combat_task_ids"]):
        raise ValueError("research map combat tasks do not match the detailed goal")
    assigned_ids = set(structure.target_role_assignments)
    observed_ids = set(structure.target_observations)
    mapped_ids = {
        target_id
        for capacity in structure.capacity_nodes
        for target_id in capacity.target_ids
    }
    checks = {
        "target role assignments": assigned_ids,
        "target observations": observed_ids,
        "capacity mappings": mapped_ids,
    }
    for label, actual in checks.items():
        missing = sorted(benchmark_ids - actual)
        unknown = sorted(actual - benchmark_ids)
        if missing or unknown:
            details = []
            if missing:
                details.append("missing=" + ",".join(missing))
            if unknown:
                details.append("unknown=" + ",".join(unknown))
            raise ValueError(f"{label} do not match fixed physical targets: {'; '.join(details)}")
    return {
        "validated": True,
        "goal_id": structure.goal_id,
        "structure_id": structure.structure_id,
        "physical_target_count": len(target_ids),
        "quantitative_subtarget_count": len(benchmark_ids),
        "combat_task_count": len(structure.combat_tasks),
        "capacity_count": len(structure.capacity_nodes),
        "diagnostic_node_count": len(structure.diagnostic_nodes),
        "intervention_node_count": len(structure.intervention_nodes),
        "relationship_status": structure.relationship_status,
    }


def load_goal_research_map(
    goal: dict[str, Any], *, project_root: Path
) -> GoalResearchMap:
    reference = goal.get("research_structure")
    if not isinstance(reference, dict) or reference.get("kind") != "linked_maps":
        raise ValueError("fixed goal does not reference a linked research map")
    relative_path = reference.get("path")
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ValueError("fixed goal research map path is missing")
    root = project_root.resolve()
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("fixed goal research map must stay inside the project") from exc
    if not path.is_file():
        raise ValueError(f"fixed goal research map is missing: {relative_path}")
    structure = GoalResearchMap.model_validate_json(path.read_text(encoding="utf-8"))
    if structure.schema_version != reference.get("schema_version"):
        raise ValueError("fixed goal and research map schema versions differ")
    validate_goal_research_map(goal, structure)
    return structure


def summarize_goal_research_map(structure: GoalResearchMap) -> dict[str, Any]:
    return {
        "structure_id": structure.structure_id,
        "kind": structure.kind,
        "relationship_status": structure.relationship_status,
        "whole_person_views": [item.model_dump(mode="json") for item in structure.whole_person_views],
        "goal_constraints": [item.model_dump(mode="json") for item in structure.goal_constraints],
        "combat_tasks": [
            {"id": item.id, "name": item.name, "capacity_ids": list(item.capacity_ids)}
            for item in structure.combat_tasks
        ],
        "capacity_nodes": [
            {
                "id": item.id,
                "success_target_id": item.success_target_id,
                "name": item.name,
                "benchmark_ids": list(item.target_ids),
            }
            for item in structure.capacity_nodes
        ],
        "boundaries": list(structure.boundaries),
    }


def expand_goal_research_map(
    structure: GoalResearchMap,
    *,
    target_ids: list[str] | None = None,
    benchmark_ids: list[str] | None = None,
    capacity_ids: list[str] | None = None,
    combat_task_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Return the smallest connected subgraph useful for a research question."""
    requested_targets = set(target_ids or [])
    requested_benchmarks = set(benchmark_ids or [])
    requested_capacities = set(capacity_ids or [])
    requested_tasks = set(combat_task_ids or [])
    if not (requested_targets or requested_benchmarks or requested_capacities or requested_tasks):
        return {
            "mode": "summary",
            "map": summarize_goal_research_map(structure),
            "interpretation_boundary": (
                "Passive whole-person routing context; no causal conclusion or strategy activation."
            ),
        }

    known_targets = {item.success_target_id for item in structure.capacity_nodes}
    known_benchmarks = set(structure.target_role_assignments)
    known_capacities = {item.id for item in structure.capacity_nodes}
    known_tasks = {item.id for item in structure.combat_tasks}
    unknowns = {
        "target": sorted(requested_targets - known_targets),
        "benchmark": sorted(requested_benchmarks - known_benchmarks),
        "capacity": sorted(requested_capacities - known_capacities),
        "combat task": sorted(requested_tasks - known_tasks),
    }
    errors = [f"unknown {label} IDs: {', '.join(ids)}" for label, ids in unknowns.items() if ids]
    if errors:
        raise ValueError("; ".join(errors))

    capacity_by_id = {item.id: item for item in structure.capacity_nodes}
    capacity_by_success_target = {
        item.success_target_id: item for item in structure.capacity_nodes
    }
    task_by_id = {item.id: item for item in structure.combat_tasks}
    selected_capacity_ids = set(requested_capacities)
    selected_capacity_ids.update(
        capacity_by_success_target[target_id].id for target_id in requested_targets
    )
    for capacity in structure.capacity_nodes:
        if requested_benchmarks.intersection(capacity.target_ids):
            selected_capacity_ids.add(capacity.id)
    for task_id in requested_tasks:
        selected_capacity_ids.update(task_by_id[task_id].capacity_ids)

    selected_task_ids = set(requested_tasks)
    selected_task_ids.update(
        task.id
        for task in structure.combat_tasks
        if selected_capacity_ids.intersection(task.capacity_ids)
    )

    related_benchmark_ids = set(requested_benchmarks)
    if requested_targets or requested_capacities or requested_tasks:
        for capacity_id in selected_capacity_ids:
            related_benchmark_ids.update(capacity_by_id[capacity_id].target_ids)

    return {
        "mode": "connected_subgraph",
        "requested": {
            "target_ids": sorted(requested_targets),
            "benchmark_ids": sorted(requested_benchmarks),
            "capacity_ids": sorted(requested_capacities),
            "combat_task_ids": sorted(requested_tasks),
        },
        "whole_person_views": [item.model_dump(mode="json") for item in structure.whole_person_views],
        "goal_constraints": [item.model_dump(mode="json") for item in structure.goal_constraints],
        "combat_tasks": [
            task_by_id[item_id].model_dump(mode="json") for item_id in sorted(selected_task_ids)
        ],
        "capacity_nodes": [
            capacity_by_id[item_id].model_dump(mode="json")
            for item_id in sorted(selected_capacity_ids)
        ],
        "benchmark_roles": {
            item_id: structure.target_role_assignments[item_id].model_dump(mode="json")
            for item_id in sorted(related_benchmark_ids)
        },
        "diagnostic_nodes": [
            item.model_dump(mode="json")
            for item in structure.diagnostic_nodes
            if selected_capacity_ids.intersection(item.capacity_ids)
        ],
        "intervention_nodes": [
            item.model_dump(mode="json")
            for item in structure.intervention_nodes
            if selected_capacity_ids.intersection(item.capacity_ids)
        ],
        "observation_semantics": structure.observation_semantics.model_dump(
            mode="json", by_alias=True
        ),
        "benchmark_observations": {
            item_id: structure.target_observations[item_id].model_dump(
                mode="json", by_alias=True
            )
            for item_id in sorted(related_benchmark_ids)
        },
        "boundaries": list(structure.boundaries),
        "interpretation_boundary": (
            "Links route research and comparisons. They do not prove personal causality, predict adaptation, "
            "or authorize an intervention."
        ),
    }


__all__ = [name for name in globals() if not name.startswith("_")]
