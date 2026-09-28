"""Internal workspace implementation, grouped by responsibility."""
from __future__ import annotations

import json
from typing import Any
from frontier_research_harness.research_contracts import ResearchStatement
from frontier_research_harness.model_relevance import candidate_targets, model_layer, required_layers
from frontier_research_harness.external_models.model_registry import unified_model_registry
from ._workspace_common import (
    EVIDENCE_CONTENT_LEVELS,
    GOAL_COVERAGE_STATUSES,
    PROJECT_ROOT,
    TECHNICAL_GOAL_TARGET_ID,
    TRACEABLE_RESEARCH_SECTIONS,
    _goal_benchmark_ids,
    _goal_physical_target_ids,
    _goal_target_benchmarks,
    _utc_now,
    _validate_tool_input,
)


class WorkspaceAuditMixin:
    def audit_research(self, target_ids: list[str] | None = None) -> dict[str, Any]:
        """Expose traceability and personal-data gaps without assigning truth scores."""
        document, updated_at = self._load_document()
        goal = document.get("fixed_goal")
        if not isinstance(goal, dict):
            raise ValueError("research audit requires a structured fixed goal")
        goal_targets = _goal_physical_target_ids(goal)
        if goal.get("technical_goal"):
            goal_targets.add(TECHNICAL_GOAL_TARGET_ID)
        all_selectable = goal_targets | _goal_benchmark_ids(goal)
        requested = goal_targets if target_ids is None else {str(item).strip() for item in target_ids}
        unknown = sorted(requested - all_selectable)
        if unknown:
            raise ValueError("unknown target IDs: " + ", ".join(unknown))
        target_benchmarks = _goal_target_benchmarks(goal)

        evidence_rows = self.connection.execute(
            "SELECT evidence_id,classification,record_json FROM frontier_science_evidence"
        ).fetchall()
        evidence = [
            {
                "evidence_id": str(row["evidence_id"]),
                "classification": str(row["classification"]),
                "record": json.loads(row["record_json"]),
            }
            for row in evidence_rows
        ]
        scholarly = [
            item for item in evidence
            if item["classification"] in {"EXTERNAL_RESEARCH", "EXTERNAL_GUIDELINE"}
        ]
        full_text_count = sum(
            item["record"].get("content_level") in {"full_text", "guideline_text"}
            for item in scholarly
        )
        current_contract_count = sum(
            item["record"].get("contract_version") == 2
            and bool(item["record"].get("target_ids"))
            and bool(item["record"].get("evidence_passages"))
            and bool(item["record"].get("quality_appraisal"))
            for item in scholarly
        )

        observation_rows = self.connection.execute(
            "SELECT observation_id,protocol_hash,record_json FROM frontier_science_personal_observations"
        ).fetchall()
        observations = [
            {
                "observation_id": str(row["observation_id"]),
                "protocol_hash": str(row["protocol_hash"]),
                "record": json.loads(row["record_json"]),
            }
            for row in observation_rows
        ]
        protocol_counts: dict[str, int] = {}
        for item in observations:
            protocol_counts[item["protocol_hash"]] = protocol_counts.get(item["protocol_hash"], 0) + 1

        statement_items: list[tuple[str, Any]] = [
            (section, item)
            for section in TRACEABLE_RESEARCH_SECTIONS
            for item in document.get(section, [])
        ]
        traceable_statements = []
        for section, item in statement_items:
            if not isinstance(item, dict):
                continue
            try:
                validated = _validate_tool_input(ResearchStatement, item)
            except ValueError:
                continue
            traceable_statements.append((section, validated.model_dump(mode="json")))

        calculation_rows = self.connection.execute(
            "SELECT calculation_id,target_id FROM frontier_science_calculations"
        ).fetchall()
        calculations = [dict(row) for row in calculation_rows]

        def related_ids(target_id: str) -> set[str]:
            return {target_id} | target_benchmarks.get(target_id, set())

        target_support = []
        for target_id in sorted(requested):
            related = related_ids(target_id)
            evidence_ids = [
                item["evidence_id"] for item in evidence
                if related.intersection(item["record"].get("target_ids", []))
            ]
            observation_ids = [
                item["observation_id"] for item in observations
                if related.intersection(item["record"].get("target_ids", []))
            ]
            calculation_ids = [
                str(item["calculation_id"]) for item in calculations
                if str(item["target_id"]) in related
            ]
            statements = [
                item for section, item in traceable_statements
                if related.intersection(item["target_ids"])
            ]
            method_count = sum(
                section == "promising_methods"
                and bool(related.intersection(item["target_ids"]))
                for section, item in traceable_statements
            )
            gaps = []
            if not evidence_ids:
                gaps.append("NO_TARGET_LINKED_EVIDENCE")
            if not observation_ids:
                gaps.append("NO_PERSONAL_OBSERVATION")
            if not statements:
                gaps.append("NO_TRACEABLE_RETAINED_STATEMENT")
            if not method_count:
                gaps.append("NO_EVIDENCE_LINKED_PROMISING_METHOD")
            target_support.append({
                "target_id": target_id,
                "evidence_count": len(evidence_ids),
                "personal_observation_count": len(observation_ids),
                "calculation_count": len(calculation_ids),
                "traceable_statement_count": len(statements),
                "promising_method_count": method_count,
                "gaps": gaps,
            })

        scholarly_count = len(scholarly)
        return {
            "audited_at": _utc_now(),
            "workspace_updated_at": updated_at,
            "literature_quality": {
                "retained_scholarly_evidence_count": scholarly_count,
                "full_text_or_guideline_count": full_text_count,
                "abstract_or_registry_count": sum(
                    item["record"].get("content_level")
                    in {"record_with_abstract", "structured_registry_record"}
                    for item in scholarly
                ),
                "current_traceability_contract_count": current_contract_count,
                "legacy_or_incomplete_count": scholarly_count - current_contract_count,
                "full_text_ratio": (
                    full_text_count / scholarly_count if scholarly_count else None
                ),
                "traceability_contract_ratio": (
                    current_contract_count / scholarly_count if scholarly_count else None
                ),
                "note": (
                    "These are structural diagnostics. They do not score study truth, effect size, "
                    "risk of bias, or applicability."
                ),
            },
            "personalization": {
                "personal_observation_count": len(observations),
                "comparable_protocol_count": len(protocol_counts),
                "repeated_comparable_protocol_count": sum(
                    count >= 2 for count in protocol_counts.values()
                ),
                "observed_target_ids": sorted({
                    target_id
                    for item in observations
                    for target_id in item["record"].get("target_ids", [])
                }),
                "note": (
                    "Repeated comparable observations support descriptive calibration only; "
                    "they are not a validated personal forecast."
                ),
            },
            "research_traceability": {
                "retained_statement_count": len(statement_items),
                "structured_statement_count": len(traceable_statements),
                "plain_text_statement_count": (
                    len(statement_items) - len(traceable_statements)
                ),
                "note": (
                    "Plain hypotheses, inferences, and unknowns are allowed. Strong typed claims "
                    "retain matching receipts."
                ),
            },
            "goal_support": {
                "targets": target_support,
                "target_count": len(target_support),
                "targets_with_evidence": sum(
                    item["evidence_count"] > 0 for item in target_support
                ),
                "targets_with_personal_observations": sum(
                    item["personal_observation_count"] > 0 for item in target_support
                ),
                "targets_with_promising_methods": sum(
                    item["promising_method_count"] > 0 for item in target_support
                ),
                "interpretation_boundary": (
                    "Support availability only; this is not a completion gate, feasibility score, "
                    "strategy activation, or prediction that the North Star will be reached."
                ),
            },
        }

    def _available_model_ids(self) -> set[str]:
        available = {"human_gem", "mitocore", "mitochondria_qsp"}
        available.update(
            item.model_id
            for item in unified_model_registry(PROJECT_ROOT).records
            if item.runtime_status.value == "READY" and model_layer(item.model_id) is not None
        )
        return available

    def _known_research_target_ids(self) -> set[str]:
        document, _ = self._load_document()
        goal = document.get('fixed_goal') or {}
        ids = self._known_goal_target_ids() | self._known_benchmark_ids()
        if goal.get('goal_id'):
            ids.add(goal['goal_id'])
        return ids

    def _known_goal_target_ids(self) -> set[str]:
        document, _ = self._load_document()
        goal = document.get('fixed_goal') or {}
        result = _goal_physical_target_ids(goal)
        if goal.get("technical_goal"):
            result.add(TECHNICAL_GOAL_TARGET_ID)
        return result

    def _known_benchmark_ids(self) -> set[str]:
        document, _ = self._load_document()
        goal = document.get('fixed_goal') or {}
        return _goal_benchmark_ids(goal)

    def _routing_benchmark_ids(self, selected_ids: set[str]) -> set[str]:
        document, _ = self._load_document()
        goal = document.get('fixed_goal') or {}
        target_benchmarks = _goal_target_benchmarks(goal)
        routed: set[str] = set()
        for selected_id in selected_ids:
            routed.update(target_benchmarks[selected_id])
        return routed

    def _assess_goal_coverage(
        self,
        goal: Any,
        coverage: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate receipt references and report gaps without gating research."""
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

        goal_target_ids = _goal_physical_target_ids(goal)
        if goal.get("technical_goal"):
            goal_target_ids.add(TECHNICAL_GOAL_TARGET_ID)
        if not goal_target_ids:
            raise ValueError("fixed goal exposes no research target IDs")
        benchmark_ids = _goal_benchmark_ids(goal)
        selectable_target_ids = goal_target_ids | benchmark_ids
        target_benchmarks = _goal_target_benchmarks(goal)

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
            unknown_requested = sorted(expected_target_ids - selectable_target_ids)
            if unknown_requested:
                raise ValueError(
                    "unknown requested goal target IDs: " + ", ".join(unknown_requested)
                )

        seen: set[str] = set()
        referenced_evidence: set[str] = set()
        referenced_experiments: set[str] = set()
        referenced_calculations: set[str] = set()
        technical_evidence: set[str] = set()
        evidence_by_target: dict[str, list[str]] = {}
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
            evidence_ids = item.get("evidence_ids", [])
            if not isinstance(evidence_ids, list):
                raise ValueError(f"{target_id} evidence_ids must be an array of strings")
            if any(not isinstance(value, str) or not value.strip() for value in evidence_ids):
                raise ValueError(f"{target_id} evidence_ids must be non-empty strings")
            if item.get("status") == "researched" and not evidence_ids:
                raise ValueError(
                    f"{target_id} marked researched requires retained evidence_ids"
                )
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
            evidence_by_target[target_id] = list(evidence_ids)
            if target_id == TECHNICAL_GOAL_TARGET_ID:
                technical_evidence.update(evidence_ids)

        missing_targets = sorted(expected_target_ids - seen)

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
        mismatched_evidence = []
        for target_id, evidence_ids in evidence_by_target.items():
            compatible_ids = {target_id} | target_benchmarks[target_id]
            for evidence_id in evidence_ids:
                evidence_targets = set(
                    evidence_record_by_id[evidence_id].get("target_ids", [])
                )
                if not compatible_ids.intersection(evidence_targets):
                    mismatched_evidence.append(f"{evidence_id} -> {target_id}")
        if mismatched_evidence:
            raise ValueError(
                "retained evidence must be explicitly linked to a compatible goal target: "
                + ", ".join(sorted(mismatched_evidence))
            )
        routed_benchmark_ids = {
            benchmark_id
            for target_id in expected_target_ids
            for benchmark_id in target_benchmarks[target_id]
        }
        relevant_model_layers = {
            layer.value
            for layer in required_layers(
                routed_benchmark_ids,
                available_model_ids=self._available_model_ids(),
            )
        }
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
                if not target_benchmarks[target_id].intersection(candidate_targets(model_name)):
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
        missing_model_layers = sorted(relevant_model_layers - covered_model_layers)
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
                if calculation_targets.get(calculation_id)
                not in target_benchmarks[str(item.get("target_id"))]
            })
            if mismatched_calculations:
                raise ValueError(
                    "calculation IDs must be attached to a compatible physical target or quantitative subtarget: "
                    + ", ".join(mismatched_calculations)
                )
        technical_status = next(
            (
                item.get("status")
                for item in statuses
                if isinstance(item, dict)
                and item.get("target_id") == TECHNICAL_GOAL_TARGET_ID
            ),
            None,
        )
        if technical_status == "researched" and not any(
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
            "complete": not missing_targets and not missing_model_layers,
            "unreported_target_ids": missing_targets,
            "relevant_model_layers": sorted(relevant_model_layers),
            "covered_model_layers": sorted(covered_model_layers),
            "uncovered_model_layers": missing_model_layers,
            "routed_benchmark_count": len(routed_benchmark_ids),
            "calculation_count": len(referenced_calculations),
            "status_counts": {
                status: sum(1 for item in statuses if item.get("status") == status)
                for status in sorted(GOAL_COVERAGE_STATUSES)
            },
        }
