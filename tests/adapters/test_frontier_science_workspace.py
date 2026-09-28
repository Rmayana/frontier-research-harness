from __future__ import annotations

import tempfile
import unittest
import json
import subprocess
import sys
from pathlib import Path
from adapters.legacy_records import seed_experiment, seed_calculation
from unittest.mock import patch

from frontier_research_harness.adapters.frontier_science_workspace import FrontierScienceWorkspace


def scholarly_evidence(
    identifier: str = "123", target_ids: list[str] | None = None
) -> dict:
    fetched = {
        "source": "pubmed",
        "identifier": identifier,
        "title": "Decision-relevant training evidence",
        "abstract": "A retained abstract used by the test.",
        "content_level": "record_with_abstract",
    }
    return {
        "source": "pubmed",
        "identifier": identifier,
        "reference_url": f"https://pubmed.ncbi.nlm.nih.gov/{identifier}/",
        "classification": "EXTERNAL_RESEARCH",
        "title": fetched["title"],
        "content_level": fetched["content_level"],
        "retained_claims": ["The source supports one bounded test claim."],
        "applicability": "Used only for the selected target in this test.",
        "limitations": ["Synthetic fixture, not a scientific conclusion."],
        "target_ids": target_ids or ["vo2max"],
        "evidence_passages": [{
            "excerpt": fetched["abstract"],
            "locator": "abstract",
            "supports_claim": "The source supports one bounded test claim.",
        }],
        "quality_appraisal": {
            "source_type": "synthetic test record",
            "population": "synthetic fixture",
            "methods": "fixture construction",
            "results": "one bounded fixture claim",
            "directness": "indirect",
            "bias_or_quality_limits": ["Synthetic fixture, not scientific evidence."],
        },
        "fetched_record": fetched,
    }


def research_item(statement: str, target_id: str = "vo2max", **receipts: object) -> dict:
    return {
        "statement": statement,
        "support_status": receipts.pop("support_status", "UNKNOWN"),
        "target_ids": [target_id],
        **receipts,
    }


class FrontierScienceWorkspaceTests(unittest.TestCase):
    def setUp(self):
        # Legacy contract tests must not force the user's live goal back to v3.
        from frontier_research_harness.adapters import _workspace_common as module
        goal = json.loads((Path(__file__).parents[1] / 'fixtures/legacy-detailed-goal.json').read_text(encoding='utf-8'))
        bootstrap = FrontierScienceWorkspace._bootstrap_document
        read_record = module._read_json_record
        def seed(workspace):
            document = bootstrap(workspace)
            document['fixed_goal'] = goal
            return document
        bootstrap_patch = patch.object(FrontierScienceWorkspace, '_bootstrap_document', seed)
        read_patch = patch.object(module, '_read_json_record', side_effect=lambda path: goal if path == module.PROJECT_ROOT / 'goal.json' else read_record(path))
        for patcher in (bootstrap_patch, read_patch):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_workspace_merges_without_revision_or_phase(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            first = workspace.load_research()
            self.assertIn("workspace", first)
            self.assertTrue(first["context_status"]["stored_content_may_be_stale"])
            self.assertTrue(first["context_status"]["verify_time_sensitive_claims"])
            self.assertEqual(
                first["context_status"]["workspace_updated_at"], first["updated_at"]
            )
            saved = workspace.save_research({"research_notes": [research_item("test note")]})
            workspace.save_research({"research_notes": [research_item("second note")], "current_state": {"sleep": {"hours": 8}}})
            workspace.save_research({"research_notes": [research_item("test note")], "current_state": {"sleep": {"quality": "good"}}})
            loaded = workspace.load_research(sections=["research_notes", "current_state"])
            self.assertEqual(
                [item["statement"] for item in loaded["workspace"]["research_notes"]],
                ["test note", "second note"],
            )
            self.assertEqual(loaded["workspace"]["current_state"]["sleep"], {"hours": 8, "quality": "good"})
            self.assertEqual(saved["updated_sections"], ["research_notes"])
            self.assertNotIn("revision", saved)
            self.assertNotIn("phase", saved)

    def test_default_context_summarizes_goal_and_can_select_sections(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            loaded = workspace.load_research()
            self.assertTrue(loaded["workspace"]["fixed_goal"]["full_goal_available"])
            self.assertNotIn("source_items", loaded["workspace"]["fixed_goal"])
            self.assertNotIn("measurements", loaded["workspace"])
            self.assertNotIn("research_protocols", loaded["workspace"])
            self.assertEqual(
                len(loaded["workspace"]["fixed_goal"]["physical_targets"]), 7
            )
            self.assertEqual(
                len(loaded["workspace"]["fixed_goal"]["measurement_benchmarks"]), 27
            )
            self.assertEqual(
                loaded["workspace"]["fixed_goal"]["technical_goal"]["reference_athlete"],
                "Artur Beterbiev",
            )
            self.assertEqual(
                loaded["workspace"]["fixed_goal"]["research_structure"]["kind"],
                "linked_maps",
            )
            self.assertEqual(
                len(loaded["workspace"]["fixed_goal"]["research_structure_summary"]["capacity_nodes"]),
                7,
            )
            self.assertNotIn("whole_body_coverage", loaded["workspace"]["fixed_goal"])
            alias = workspace.load_research(sections=["goal", "state"])
            self.assertIn("fixed_goal", alias["workspace"])
            self.assertIn("current_state", alias["workspace"])
            research_alias = workspace.load_research(sections=["research"])
            self.assertIn("research_notes", research_alias["workspace"])
            with self.assertRaisesRegex(ValueError, "unknown research sections"):
                workspace.load_research(sections=["research_protocols"])

    def test_goal_map_expands_a_target_through_separate_linked_views(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            overview = workspace.load_goal_map()
            self.assertEqual(overview["mode"], "summary")
            self.assertTrue(overview["validation"]["validated"])
            self.assertEqual(overview["validation"]["physical_target_count"], 7)
            self.assertEqual(overview["validation"]["quantitative_subtarget_count"], 27)

            expanded = workspace.load_goal_map(benchmark_ids=["cmj_height"])
            self.assertEqual(expanded["mode"], "connected_subgraph")
            self.assertEqual(expanded["requested"]["benchmark_ids"], ["cmj_height"])
            self.assertEqual(
                {item["id"] for item in expanded["capacity_nodes"]},
                {"impulse_power"},
            )
            self.assertIn("cmj_height", expanded["benchmark_observations"])
            self.assertTrue(expanded["diagnostic_nodes"])
            self.assertTrue(expanded["intervention_nodes"])
            self.assertIn("do not prove personal causality", expanded["interpretation_boundary"])

            with self.assertRaisesRegex(ValueError, "unknown target IDs"):
                workspace.load_goal_map(target_ids=["not_a_goal_target"])

    def test_existing_workspace_imports_missing_personal_context(self):
        with tempfile.TemporaryDirectory() as root:
            profile = Path(root) / "profile.json"
            body = Path(root) / "body.json"
            profile.write_text(json.dumps({"height_cm": 191, "uncertainty": ["test"]}), encoding="utf-8")
            body.write_text(json.dumps({"body_mass_kg": 79.4, "measurement_uncertainty": ["test"]}), encoding="utf-8")
            database = Path(root) / "research.sqlite3"
            with patch("frontier_research_harness.adapters._workspace_common.PERSONAL_PROFILE", profile), patch("frontier_research_harness.adapters._workspace_common.BODY_COMPOSITION_BASELINE", body):
                with FrontierScienceWorkspace(database) as workspace:
                    workspace.save_research({"current_state": {"sleep": {"hours": 8}}})
                profile.write_text(json.dumps({"height_cm": 192, "uncertainty": ["updated test"]}), encoding="utf-8")
                with FrontierScienceWorkspace(database) as workspace:
                    state = workspace.load_research(sections=["current_state"])["workspace"]["current_state"]
            self.assertEqual(state["sleep"]["hours"], 8)
            self.assertEqual(state["personal_profile"]["height_cm"], 192)
            self.assertEqual(state["body_composition_baseline"]["body_mass_kg"], 79.4)
            self.assertEqual(state["personal_profile"]["provenance"]["kind"], "local_user_record")

    def test_unknown_workspace_objects_are_rejected(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            with self.assertRaisesRegex(ValueError, "unknown research sections"):
                workspace.save_research({"planner": {"next": "invented workflow"}})

    def test_plain_hypotheses_are_allowed_but_strong_labels_require_receipts(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            workspace.save_research({
                "hypotheses": [
                    "A tentative mechanism can stay plain while it is being explored.",
                    {
                        "statement": "A typed hypothesis does not need a target or receipt.",
                        "support_status": "HYPOTHESIS",
                    },
                ]
            })
            loaded = workspace.load_research(sections=["hypotheses"])
            self.assertEqual(len(loaded["workspace"]["hypotheses"]), 2)
            with self.assertRaisesRegex(ValueError, "SUPPORTED requires"):
                workspace.save_research({
                    "research_notes": [research_item(
                        "unsupported claim", support_status="SUPPORTED"
                    )]
                })

    def test_multiple_chat_research_topics_can_share_one_workspace(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            workspace.save_research({
                "hypotheses": [
                    research_item("best training route for neck strength", "neck_flexion_force", support_status="HYPOTHESIS"),
                    research_item("best training route for choice reaction", "choice_reaction_time", support_status="HYPOTHESIS"),
                ],
                "research_notes": [
                    research_item("synthesize interactions after separate research")
                ],
            })
            loaded = workspace.load_research(sections=["hypotheses", "research_notes"])
            self.assertEqual(len(loaded["workspace"]["hypotheses"]), 2)
            self.assertEqual(
                loaded["workspace"]["research_notes"][0]["statement"],
                "synthesize interactions after separate research",
            )


    def test_literature_portfolio_preserves_queries_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            with patch(
                "frontier_research_harness.adapters._workspace_evidence.ScientificKnowledgeClient"
            ) as client_type:
                client_type.return_value.search.side_effect = (
                    {"source": "pubmed", "query": "mechanism", "results": [{"id": "1", "doi": "10.1/shared", "title": "Shared"}]},
                    {"source": "europe_pmc", "query": "contrary", "results": [{"id": "1", "doi": "10.1/shared", "title": "Shared"}, {"id": "2", "title": "Contrary"}]},
                )
                result = workspace.search_literature_portfolio([
                    {"source": "pubmed", "query": "mechanism"},
                    {"source": "europe_pmc", "query": "contrary"},
                ])
            self.assertEqual(result["unique_result_count"], 2)
            self.assertEqual(len(result["searches"]), 2)
            self.assertNotIn("quality_score", result)

    def test_literature_queries_isolate_failures_and_return_next_queries(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            with patch(
                "frontier_research_harness.adapters._workspace_evidence.ScientificKnowledgeClient"
            ) as client_type:
                client_type.return_value.search.side_effect = (
                    RuntimeError("temporary source failure"),
                    {"source": "europe_pmc", "query": "power", "results": [{"id": "2", "title": "Power"}], "returned_count": 1, "next_cursor": "next"},
                )
                result = workspace.search_literature_portfolio([
                    {"source": "pubmed", "query": "force"},
                    {"source": "europe_pmc", "query": "power"},
                ])
            self.assertEqual(result["failed_search_count"], 1)
            self.assertEqual(result["completed_search_count"], 1)
            self.assertEqual(result["unique_result_count"], 1)
            self.assertEqual(result["next_queries"][0]["cursor"], "next")
            self.assertFalse(result["searches"][0]["ok"])

    def test_evidence_is_deduplicated_and_loadable(self):
        record = scholarly_evidence()
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            first = workspace.save_evidence(record)
            second = workspace.save_evidence(record)
            changed = workspace.save_evidence({
                **record,
                "content_level": "full_text",
                "fetched_record": {**record["fetched_record"], "content_level": "full_text", "body": "full"},
            })
            loaded = workspace.load_evidence(first["evidence_id"])
            context = workspace.load_research()
        self.assertFalse(first["deduplicated"])
        self.assertTrue(second["deduplicated"])
        self.assertEqual(first["evidence_id"], second["evidence_id"])
        self.assertFalse(changed["deduplicated"])
        self.assertNotEqual(first["evidence_id"], changed["evidence_id"])
        self.assertEqual(loaded["record"]["fetched_record"]["content_level"], "record_with_abstract")
        self.assertEqual(len(loaded["record"]["content_sha256"]), 64)
        self.assertEqual(context["evidence_count"], 2)

    def test_metadata_only_or_claimless_evidence_is_rejected(self):
        record = scholarly_evidence()
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            with self.assertRaisesRegex(ValueError, "unsupported evidence content_level"):
                workspace.save_evidence({
                    **record,
                    "content_level": "metadata",
                    "fetched_record": {**record["fetched_record"], "content_level": "metadata"},
                })
            with self.assertRaisesRegex(ValueError, "retained_claims"):
                workspace.save_evidence({**record, "retained_claims": []})

    def test_selected_goal_coverage_maps_real_evidence_and_reports_omissions(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            evidence_id = workspace.save_evidence(scholarly_evidence())["evidence_id"]
            with patch.object(workspace, "_execute", create=True, return_value=("test-v1", {"value": 1})):
                pulse_id = seed_experiment(workspace,
                    "pulse",
                    {"value": 1},
                    question="What bounded result informs the selected target?",
                    provenance=[{"kind": "TEST"}],
                )["experiment_id"]
                circadapt_id = seed_experiment(workspace,
                    "circadapt", {"value": 2},
                    question="What organ boundary informs the selected target?",
                    provenance=[{"kind": "TEST"}],
                )["experiment_id"]
            selected = workspace.save_research(
                {"research_notes": [research_item("selected target researched")]},
                coverage={
                    "scope": "selected_targets",
                    "requested_target_ids": ["vo2max"],
                    "target_statuses": [{
                        "target_id": "vo2max",
                        "status": "researched",
                        "finding": "The evidence was inspected for this target.",
                        "evidence_ids": [evidence_id],
                        "experiment_ids": [pulse_id, circadapt_id],
                    }],
                },
            )
            self.assertTrue(selected["research_coverage"]["validated"])
            self.assertEqual(selected["research_coverage"]["target_count"], 1)
            self.assertEqual(selected["research_coverage"]["experiment_model_count"], 2)
            incomplete = workspace.save_research(
                {"research_notes": [research_item("incomplete whole goal")]},
                coverage={
                    "scope": "whole_goal",
                    "target_statuses": [{
                        "target_id": "fatigue_resistance_recovery",
                        "status": "researched",
                        "finding": "Only one target was covered.",
                        "evidence_ids": [evidence_id],
                        "experiment_ids": [pulse_id, circadapt_id],
                    }],
                },
            )
            self.assertFalse(incomplete["research_coverage"]["complete"])
            self.assertIn(
                "technical_goal",
                incomplete["research_coverage"]["unreported_target_ids"],
            )

    def test_coverage_rejects_legacy_identifier_only_evidence(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            legacy_id = "legacy-evidence"
            workspace.connection.execute(
                "INSERT INTO frontier_science_evidence(evidence_id,created_at,source,identifier,reference_url,classification,record_json) VALUES(?,?,?,?,?,?,?)",
                (
                    legacy_id,
                    "2026-01-01T00:00:00+00:00",
                    "pubmed",
                    "1",
                    "https://pubmed.ncbi.nlm.nih.gov/1/",
                    "EXTERNAL_RESEARCH",
                    json.dumps({
                        "source": "pubmed",
                        "reference_url": "https://pubmed.ncbi.nlm.nih.gov/1/",
                        "classification": "EXTERNAL_RESEARCH",
                    }),
                ),
            )
            with patch.object(workspace, "_execute", create=True, return_value=("test-v1", {"value": 1})):
                experiment_id = seed_experiment(workspace,
                    "test_model",
                    {"value": 1},
                    question="What bounded result informs the target?",
                    provenance=[{"kind": "TEST"}],
                )["experiment_id"]
            with self.assertRaisesRegex(ValueError, "legacy or incomplete evidence"):
                workspace.save_research(
                    {"research_notes": [research_item("legacy evidence must not pass")]},
                    coverage={
                        "scope": "selected_targets",
                        "requested_target_ids": ["vo2max"],
                        "target_statuses": [{
                            "target_id": "vo2max",
                            "status": "unresolved",
                            "finding": "The old record contains no reusable content.",
                            "evidence_ids": [legacy_id],
                            "experiment_ids": [experiment_id],
                        }],
                    },
                )

    def test_unresolved_coverage_can_report_missing_evidence_and_models(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            saved = workspace.save_research(
                {"research_notes": [research_item("The target remains unresolved.", "cmj_height")]},
                coverage={
                    "scope": "selected_targets",
                    "requested_target_ids": ["cmj_height"],
                    "target_statuses": [{
                        "target_id": "cmj_height",
                        "status": "unresolved",
                        "finding": "No decision-relevant personal observation is available.",
                        "evidence_ids": [],
                    }],
                },
            )
            assessment = saved["research_coverage"]
            self.assertTrue(assessment["validated"])
            self.assertFalse(assessment["complete"])
            self.assertEqual(assessment["evidence_count"], 0)
            self.assertTrue(assessment["uncovered_model_layers"])


    def test_active_import_keeps_removed_modules_absent(self):
        code = """
import json
import sys
import frontier_research_harness.adapters.scientific_model_mcp
blocked = [
    name for name in sys.modules
    if name.startswith('frontier_research_harness.kernel')
    or name.endswith('precision_whole_body_simulator')
    or name.endswith('research_learning')
    or name.endswith('frontier_discovery')
]
print(json.dumps(blocked))
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(result.stdout), [])


    def test_technical_only_coverage_uses_primary_footage_without_a_model(self):
        footage = {
            "source": "fight-footage",
            "reference_url": "https://example.test/fight",
            "identifier": "round-1",
            "classification": "EXTERNAL_PRIMARY_SOURCE",
            "title": "Timestamped fight observation",
            "content_level": "primary_source_observation",
            "retained_claims": ["00:10 pressure step preceded the body attack."],
            "applicability": "One bounded observation of the named athlete.",
            "limitations": ["Single camera angle."],
            "target_ids": ["technical_goal"],
            "source_record": {"timestamp": "00:10", "observation": "pressure step"},
        }
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            evidence_id = workspace.save_evidence(footage)["evidence_id"]
            saved = workspace.save_research(
                {"research_notes": [research_item("Technique footage retained without irrelevant simulation.", "technical_goal")]},
                coverage={
                    "scope": "selected_targets",
                    "requested_target_ids": ["technical_goal"],
                    "target_statuses": [{
                        "target_id": "technical_goal",
                        "status": "researched",
                        "finding": "One timestamped technique observation was retained.",
                        "evidence_ids": [evidence_id],
                    }],
                },
            )
            self.assertTrue(saved["research_coverage"]["validated"])
            self.assertEqual(saved["research_coverage"]["experiment_count"], 0)

    def test_coverage_accepts_only_calculations_for_the_matching_target(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            evidence_id = workspace.save_evidence(
                scholarly_evidence(target_ids=["imtp_peak_force", "vo2max"])
            )["evidence_id"]
            calculation_id = seed_calculation(workspace,
                "imtp_peak_force",
                {"peak_force_n": 7200.0, "body_mass_kg": 120.0},
                units={"peak_force_n": "N", "body_mass_kg": "kg"},
            )["calculation_id"]
            with patch.object(workspace, "_execute", create=True, return_value=("test-v1", {"value": 1})):
                experiment_id = seed_experiment(workspace,
                    "opensim", {"value": 1}, question="What bounded result informs strength?",
                    provenance=[{"kind": "TEST"}],
                )["experiment_id"]
            saved = workspace.save_research(
                {"research_notes": [research_item("Calculation attached to its target.", "simple_visual_reaction_time")]},
                coverage={
                    "scope": "selected_targets",
                    "requested_target_ids": ["imtp_peak_force"],
                    "target_statuses": [{
                        "target_id": "imtp_peak_force", "status": "researched",
                        "finding": "The target arithmetic was reproduced.",
                        "evidence_ids": [evidence_id],
                        "experiment_ids": [experiment_id],
                        "calculation_ids": [calculation_id],
                    }],
                },
            )
            self.assertEqual(saved["research_coverage"]["calculation_count"], 1)
            with patch.object(workspace, "_execute", create=True, return_value=("test-v1", {"value": 1})):
                pulse_id = seed_experiment(workspace,
                    "pulse", {"value": 2}, question="What systemic boundary informs VO2max?",
                    provenance=[{"kind": "TEST"}],
                )["experiment_id"]
                circadapt_id = seed_experiment(workspace,
                    "circadapt", {"value": 3}, question="What organ boundary informs VO2max?",
                    provenance=[{"kind": "TEST"}],
                )["experiment_id"]
            with self.assertRaisesRegex(ValueError, "compatible physical target"):
                workspace.save_research(
                    {"research_notes": [research_item("Mismatched calculation.", "cmj_height")]},
                    coverage={
                        "scope": "selected_targets", "requested_target_ids": ["vo2max"],
                        "target_statuses": [{
                            "target_id": "vo2max", "status": "unresolved",
                            "finding": "Wrong calculation attached.", "evidence_ids": [evidence_id],
                            "experiment_ids": [pulse_id, circadapt_id], "calculation_ids": [calculation_id],
                        }],
                    },
                )

    def test_selected_portfolio_reports_uncovered_model_layers(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            evidence_id = workspace.save_evidence(scholarly_evidence(target_ids=[
                "vo2max", "cmj_height", "major_injury_count", "wingate_peak_power"
            ]))["evidence_id"]
            with patch.object(workspace, "_execute", create=True, return_value=("test-v1", {"value": 1})):
                experiments = {
                    name: seed_experiment(workspace,
                        name, {"name": name}, question=f"What boundary does {name} establish?",
                        provenance=[{"kind": "TEST"}],
                    )["experiment_id"]
                    for name in ("pulse", "circadapt", "opensim", "febio", "mitocore")
                }
            target_statuses = [
                {"target_id": "vo2max", "status": "researched", "finding": "System and organ bounds retained.", "evidence_ids": [evidence_id], "experiment_ids": [experiments["pulse"], experiments["circadapt"]]},
                {"target_id": "cmj_height", "status": "unresolved", "finding": "Mechanical reference retained.", "evidence_ids": [evidence_id], "experiment_ids": [experiments["opensim"]]},
                {"target_id": "major_injury_count", "status": "unresolved", "finding": "Tissue reference retained.", "evidence_ids": [evidence_id], "experiment_ids": [experiments["febio"]]},
                {"target_id": "wingate_peak_power", "status": "unresolved", "finding": "Cellular reference retained.", "evidence_ids": [evidence_id], "experiment_ids": [experiments["mitocore"]]},
            ]
            coverage = {
                "scope": "selected_targets",
                "requested_target_ids": ["vo2max", "cmj_height", "major_injury_count", "wingate_peak_power"],
                "target_statuses": target_statuses,
            }
            incomplete = {**coverage, "target_statuses": [
                {**item, "experiment_ids": (
                    item["experiment_ids"] if item["target_id"] == "wingate_peak_power" else []
                )}
                for item in target_statuses
            ]}
            assessed = workspace.save_research(
                {"research_notes": [research_item("single-layer attempt")]}, coverage=incomplete
            )
            self.assertFalse(assessed["research_coverage"]["complete"])
            self.assertIn(
                "whole_person_physiology",
                assessed["research_coverage"]["uncovered_model_layers"],
            )
            saved = workspace.save_research(
                {"research_notes": [research_item("all relevant layers covered")]}, coverage=coverage
            )
            self.assertTrue(saved["research_coverage"]["complete"])
            self.assertEqual(len(saved["research_coverage"]["covered_model_layers"]), 5)



    def test_personal_observations_are_protocol_comparable_and_audited(self):
        base = {
            "target_ids": ["vo2max"],
            "metric": "VO2max",
            "unit": "ml/kg/min",
            "protocol": "same lab ramp protocol",
            "source_type": "LAB",
            "instrument": "metabolic cart A",
            "provenance": [{"kind": "TEST_FIXTURE", "record": "lab report"}],
        }
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            saved = workspace.save_personal_observations([
                {**base, "observed_at": "2026-01-01T09:00:00+09:00", "value": 45.0},
                {**base, "observed_at": "2026-02-01T09:00:00+09:00", "value": 47.5},
                {**base, "observed_at": "2026-03-01T09:00:00+09:00", "value": 48.0, "target_ids": ["not-a-target"]},
            ])
            self.assertEqual(
                saved["counts"], {"SAVED": 2, "DEDUPLICATED": 0, "INVALID": 1}
            )
            listed = workspace.list_personal_observations(target_ids=["vo2max"])
            self.assertEqual(listed["matched_count"], 2)
            self.assertEqual(listed["repeated_comparable_series_count"], 1)
            self.assertEqual(listed["series"][0]["descriptive_delta"], 2.5)

            evidence_id = workspace.save_evidence(scholarly_evidence())["evidence_id"]
            observation_id = saved["results"][0]["observation_id"]
            workspace.save_research({
                "research_notes": [research_item(
                    "One source supports a bounded VO2max claim.",
                    support_status="SUPPORTED",
                    evidence_ids=[evidence_id],
                )],
                "promising_methods": [research_item(
                    "Retain this candidate only for further research.",
                    support_status="SUPPORTED",
                    evidence_ids=[evidence_id],
                )],
                "hypotheses": [research_item(
                    "The repeated personal series may alter method selection.",
                    support_status="USER_OBSERVATION",
                    observation_ids=[observation_id],
                )],
            })
            audit = workspace.audit_research(["vo2max"])
            self.assertEqual(
                audit["literature_quality"]["current_traceability_contract_count"], 1
            )
            self.assertEqual(
                audit["personalization"]["repeated_comparable_protocol_count"], 1
            )
            support = audit["goal_support"]["targets"][0]
            self.assertEqual(support["personal_observation_count"], 2)
            self.assertEqual(support["promising_method_count"], 1)
            self.assertEqual(support["gaps"], [])

    def test_footage_observation_is_saved_as_exact_primary_evidence(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            saved = workspace.save_footage_observation({
                "source": "official fight footage", "reference_url": "https://example.test/fight-1",
                "title": "Pressure sequence", "athlete": "Artur Beterbiev",
                "opponent_or_context": "round 2", "start_seconds": 40, "end_seconds": 46,
                "observed_actions": ["lead foot blocks the lateral exit"],
                "situational_conditions": ["opponent retreats toward the ropes"],
                "repeated_pattern": True, "derived_drills": ["ring-cutting constraint sparring"],
                "applicability": "Technical goal ring cutting.",
                "limitations": ["Single angle; repetition must be checked in other bouts."],
            })
            loaded = workspace.load_evidence(saved["evidence_id"])
            self.assertEqual(loaded["classification"], "EXTERNAL_PRIMARY_SOURCE")
            self.assertEqual(loaded["record"]["source_record"]["start_seconds"], 40.0)
            self.assertEqual(saved["technical_goal_target_id"], "technical_goal")

    def test_footage_observations_can_be_listed_and_compared_without_ranking(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            ids = []
            for index, context in enumerate(("round 2", "round 7")):
                ids.append(workspace.save_footage_observation({
                    "source": "official footage", "reference_url": f"https://example.test/fight-{index}",
                    "title": f"Pressure sequence {index}", "athlete": "Artur Beterbiev",
                    "opponent_or_context": context, "start_seconds": 40, "end_seconds": 46,
                    "observed_actions": ["lead foot blocks the lateral exit"],
                    "situational_conditions": ["opponent retreats"], "repeated_pattern": True,
                    "applicability": "Ring cutting.", "limitations": ["Single angle."],
                })["evidence_id"])
            listed = workspace.list_footage_observations(athlete="artur beterbiev")
            compared = workspace.compare_footage_observations(ids)
            self.assertEqual(listed["count"], 2)
            self.assertEqual(compared["shared_actions_exact"], ["lead foot blocks the lateral exit"])
            self.assertTrue(compared["all_marked_repeated_pattern"])
            self.assertIn("Codex must judge", compared["comparison_boundary"])


if __name__ == "__main__":
    unittest.main()
