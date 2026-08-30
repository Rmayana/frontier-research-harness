from __future__ import annotations

import tempfile
import unittest
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from frontier_research_harness.adapters.frontier_science_workspace import FrontierScienceWorkspace


def scholarly_evidence(identifier: str = "123") -> dict:
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
        "fetched_record": fetched,
    }


class FrontierScienceWorkspaceTests(unittest.TestCase):
    def test_workspace_merges_without_revision_or_phase(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            first = workspace.load_research()
            self.assertIn("workspace", first)
            saved = workspace.save_research({"research_notes": ["test note"]})
            workspace.save_research({"research_notes": ["second note"], "current_state": {"sleep": {"hours": 8}}})
            workspace.save_research({"research_notes": ["test note"], "current_state": {"sleep": {"quality": "good"}}})
            loaded = workspace.load_research(sections=["research_notes", "current_state"])
            self.assertEqual(loaded["workspace"]["research_notes"], ["test note", "second note"])
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
                len(loaded["workspace"]["fixed_goal"]["physical_targets"]), 27
            )
            self.assertEqual(
                loaded["workspace"]["fixed_goal"]["technical_goal"]["reference_athlete"],
                "Artur Beterbiev",
            )
            self.assertNotIn("whole_body_coverage", loaded["workspace"]["fixed_goal"])
            alias = workspace.load_research(sections=["goal", "state"])
            self.assertIn("fixed_goal", alias["workspace"])
            self.assertIn("current_state", alias["workspace"])
            research_alias = workspace.load_research(sections=["research"])
            self.assertIn("research_notes", research_alias["workspace"])
            with self.assertRaisesRegex(ValueError, "unknown research sections"):
                workspace.load_research(sections=["research_protocols"])

    def test_existing_workspace_imports_missing_personal_context(self):
        with tempfile.TemporaryDirectory() as root:
            profile = Path(root) / "profile.json"
            body = Path(root) / "body.json"
            profile.write_text(json.dumps({"height_cm": 191, "uncertainty": ["test"]}), encoding="utf-8")
            body.write_text(json.dumps({"body_mass_kg": 79.4, "measurement_uncertainty": ["test"]}), encoding="utf-8")
            database = Path(root) / "research.sqlite3"
            with patch("frontier_research_harness.adapters.frontier_science_workspace.PERSONAL_PROFILE", profile), patch("frontier_research_harness.adapters.frontier_science_workspace.BODY_COMPOSITION_BASELINE", body):
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

    def test_multiple_chat_research_topics_can_share_one_workspace(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            workspace.save_research({
                "hypotheses": [
                    {"topic": "neck strength", "question": "best training route"},
                    {"topic": "choice reaction", "question": "best training route"},
                ],
                "research_notes": [
                    {"topic": "portfolio", "finding": "synthesize interactions after separate research"}
                ],
            })
            loaded = workspace.load_research(sections=["hypotheses", "research_notes"])
            self.assertEqual(len(loaded["workspace"]["hypotheses"]), 2)
            self.assertEqual(loaded["workspace"]["research_notes"][0]["topic"], "portfolio")

    def test_catalog_exposes_direct_external_models_and_their_contracts(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            names = {item["name"] for item in workspace.list_models()["models"]}
            self.assertTrue({"human_gem", "mitocore", "mitochondria_qsp", "registered_external_engine"} <= names)
            self.assertNotIn("fick_oxygen_transport", names)
            self.assertNotIn("scientific_range_inference", names)
            self.assertNotIn("resistance_training_candidate", names)
            self.assertTrue({"febio", "pulse", "circadapt", "pk_sim"} <= names)
            self.assertNotIn("frontier_network", names)
            self.assertNotIn("reduced_whole_body", names)
            description = workspace.describe_model("human_gem")
            self.assertTrue(description["execution_available"])
            self.assertIn("input_schema", description)
            self.assertIn("outputs", description)
            self.assertIn("limitations", description)
            self.assertIn("validation", description)
            self.assertEqual(description["research_readiness"], "RESEARCH_CALLABLE")
            self.assertFalse(description["personalized"])

    def test_catalog_routes_targets_to_every_relevant_model_layer(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            result = workspace.list_models([
                "vo2max", "cmj_height", "major_injury_count", "wingate_peak_power"
            ])
            self.assertEqual(
                set(result["required_model_layers"]),
                {
                    "whole_person_physiology", "organ_circulation",
                    "musculoskeletal_mechanics", "tissue_durability",
                    "cellular_metabolism",
                },
            )
            by_name = {item["name"]: item for item in result["models"]}
            self.assertTrue(by_name["pulse"]["target_relevant_for_current_question"])
            self.assertTrue(by_name["circadapt"]["target_relevant_for_current_question"])
            self.assertTrue(by_name["opensim"]["target_relevant_for_current_question"])
            self.assertTrue(by_name["febio"]["target_relevant_for_current_question"])
            self.assertTrue(by_name["mitocore"]["target_relevant_for_current_question"])
            self.assertFalse(by_name["pk_sim"]["target_relevant_for_current_question"])
            self.assertIn("reference_experiment", workspace.describe_model("pulse"))

    def test_literature_portfolio_preserves_queries_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            with patch(
                "frontier_research_harness.adapters.frontier_science_workspace.ScientificKnowledgeClient"
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
                "frontier_research_harness.adapters.frontier_science_workspace.ScientificKnowledgeClient"
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

    def test_selected_goal_coverage_maps_real_evidence_and_rejects_omissions(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            evidence_id = workspace.save_evidence(scholarly_evidence())["evidence_id"]
            with patch.object(workspace, "_execute", return_value=("test-v1", {"value": 1})):
                pulse_id = workspace.run_model(
                    "pulse",
                    {"value": 1},
                    question="What bounded result informs the selected target?",
                    provenance=[{"kind": "TEST"}],
                )["experiment_id"]
                circadapt_id = workspace.run_model(
                    "circadapt", {"value": 2},
                    question="What organ boundary informs the selected target?",
                    provenance=[{"kind": "TEST"}],
                )["experiment_id"]
            selected = workspace.save_research(
                {"research_notes": ["selected target researched"]},
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
            with self.assertRaisesRegex(ValueError, "omitted goal targets"):
                workspace.save_research(
                    {"research_notes": ["incomplete whole goal"]},
                    coverage={
                        "scope": "whole_goal",
                        "target_statuses": [{
                            "target_id": "vo2max",
                            "status": "researched",
                            "finding": "Only one target was covered.",
                            "evidence_ids": [evidence_id],
                            "experiment_ids": [pulse_id, circadapt_id],
                        }],
                    },
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
            with patch.object(workspace, "_execute", return_value=("test-v1", {"value": 1})):
                experiment_id = workspace.run_model(
                    "test_model",
                    {"value": 1},
                    question="What bounded result informs the target?",
                    provenance=[{"kind": "TEST"}],
                )["experiment_id"]
            with self.assertRaisesRegex(ValueError, "legacy or incomplete evidence"):
                workspace.save_research(
                    {"research_notes": ["legacy evidence must not pass"]},
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

    def test_external_inventory_exposes_typed_execution_without_claiming_personalization(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            description = workspace.describe_model("pulse")
            self.assertEqual(description["connection_status"], "READY")
            self.assertTrue(description["execution_available"])
            self.assertEqual(description["execution_via"].split("(")[0], "run_model")
            self.assertIn("input_schema", description)
            self.assertIn("outputs", description)
            self.assertEqual(description["research_readiness"], "TYPED_STUDY_CALLABLE")
            self.assertIn("research_input_schema", description)
            self.assertFalse(description["personalized"])
            self.assertNotIn("execution_note", description)
            self.assertNotIn("blockers", description)

    def test_unavailable_model_returns_only_one_short_reason(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            description = workspace.describe_model("anybody")
            self.assertFalse(description["execution_available"])
            self.assertIn("reason", description)
            self.assertNotIn("blockers", description)
            self.assertNotIn("limitations", description)
            self.assertEqual(description["validation_status"], "unqualified for personal prediction")
            self.assertEqual(description["research_readiness"], "NOT_EXECUTABLE")

    def test_model_run_is_validated_and_automatically_recorded(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            with patch.object(workspace, "_execute", return_value=("test-v1", {"trajectory": [1, 2]})):
                result = workspace.run_model(
                    "test_model",
                    {"input": 1},
                    question="Does persistence preserve this output?",
                    provenance=[{"kind": "TEST"}],
                )
            loaded = workspace.load_experiment(result["experiment_id"])
            self.assertEqual(loaded["input_hash"], result["input_hash"])
            self.assertEqual(loaded["model_version"], "test-v1")
            self.assertEqual(loaded["raw_output"]["trajectory"], [1, 2])
            self.assertEqual(workspace.list_experiments()["count"], 1)

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

    def test_external_engine_accepts_json_arrays_from_mcp(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            with patch(
                "frontier_research_harness.adapters.frontier_science_workspace.ExternalEngineRunner.run",
                return_value={"component_id": "circadapt", "exit_code": 0},
            ) as run:
                version, result = workspace._execute(
                    "registered_external_engine",
                    {
                        "component_id": "circadapt",
                        "arguments": ["driver.py"],
                        "input_artifacts": ["driver.py"],
                        "expected_output_artifacts": [],
                    },
                )
            self.assertEqual(version, "registered-engine-bridge-v1")
            self.assertEqual(result["exit_code"], 0)
            self.assertEqual(run.call_args.args[0].arguments, ("driver.py",))

    def test_ready_engine_runs_by_its_own_name(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            with patch(
                "frontier_research_harness.adapters.frontier_science_workspace.ExternalEngineRunner.run",
                return_value={"component_id": "circadapt", "exit_code": 0},
            ) as run:
                _, result = workspace._execute(
                    "circadapt",
                    {"arguments": ["driver.py"], "input_artifacts": [], "expected_output_artifacts": []},
                )
            self.assertEqual(result["component_id"], "circadapt")
            self.assertEqual(run.call_args.args[0].component_id, "circadapt")

    def test_compare_runs_returns_raw_records_without_winner(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            with patch.object(workspace, "_execute", side_effect=(("v1", {"value": 1}), ("v1", {"value": 2}))):
                ids = [
                    workspace.run_model(
                        "test_model",
                        {"value": value},
                        question="How does the test value change?",
                        provenance=[{"kind": "TEST", "value": value}],
                    )["experiment_id"]
                    for value in (1, 2)
                ]
            comparison = workspace.compare_runs(ids)
            self.assertEqual(len(comparison["runs"]), 2)
            self.assertNotIn("winner", comparison)
            self.assertEqual(comparison["runs"][0]["output_mode"], "STRUCTURAL_SUMMARY")
            self.assertNotIn("raw_output", comparison["runs"][0])
            exact = workspace.compare_runs(ids, output_paths=["value"])
            self.assertEqual(exact["runs"][1]["output"]["value"], 2)

    def test_target_calculation_is_unit_checked_persisted_and_loadable(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            result = workspace.calculate_target(
                "imtp_peak_force",
                {"peak_force_n": 7200.0, "body_mass_kg": 120.0},
                units={"peak_force_n": "N", "body_mass_kg": "kg"},
            )
            loaded = workspace.load_calculation(result["calculation_id"])
            self.assertTrue(result["persisted"])
            self.assertEqual(result["value"], 60.0)
            self.assertEqual(loaded["output"]["evidence_class"], "DATA_DERIVED")
            self.assertEqual(workspace.load_research()["calculation_count"], 1)
            missing = workspace.calculate_target("vo2max")
            self.assertFalse(missing["persisted"])
            self.assertEqual(missing["status"], "INPUT_REQUIRED")

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
            "source_record": {"timestamp": "00:10", "observation": "pressure step"},
        }
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            evidence_id = workspace.save_evidence(footage)["evidence_id"]
            saved = workspace.save_research(
                {"research_notes": ["Technique footage retained without irrelevant simulation."]},
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
            evidence_id = workspace.save_evidence(scholarly_evidence())["evidence_id"]
            calculation_id = workspace.calculate_target(
                "imtp_peak_force",
                {"peak_force_n": 7200.0, "body_mass_kg": 120.0},
                units={"peak_force_n": "N", "body_mass_kg": "kg"},
            )["calculation_id"]
            with patch.object(workspace, "_execute", return_value=("test-v1", {"value": 1})):
                experiment_id = workspace.run_model(
                    "opensim", {"value": 1}, question="What bounded result informs strength?",
                    provenance=[{"kind": "TEST"}],
                )["experiment_id"]
            saved = workspace.save_research(
                {"research_notes": ["Calculation attached to its target."]},
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
            with patch.object(workspace, "_execute", return_value=("test-v1", {"value": 1})):
                pulse_id = workspace.run_model(
                    "pulse", {"value": 2}, question="What systemic boundary informs VO2max?",
                    provenance=[{"kind": "TEST"}],
                )["experiment_id"]
                circadapt_id = workspace.run_model(
                    "circadapt", {"value": 3}, question="What organ boundary informs VO2max?",
                    provenance=[{"kind": "TEST"}],
                )["experiment_id"]
            with self.assertRaisesRegex(ValueError, "their own physical target"):
                workspace.save_research(
                    {"research_notes": ["Mismatched calculation."]},
                    coverage={
                        "scope": "selected_targets", "requested_target_ids": ["vo2max"],
                        "target_statuses": [{
                            "target_id": "vo2max", "status": "unresolved",
                            "finding": "Wrong calculation attached.", "evidence_ids": [evidence_id],
                            "experiment_ids": [pulse_id, circadapt_id], "calculation_ids": [calculation_id],
                        }],
                    },
                )

    def test_selected_portfolio_requires_all_relevant_model_layers(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            evidence_id = workspace.save_evidence(scholarly_evidence())["evidence_id"]
            with patch.object(workspace, "_execute", return_value=("test-v1", {"value": 1})):
                experiments = {
                    name: workspace.run_model(
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
            with self.assertRaisesRegex(ValueError, "missing decision-relevant external-model layers"):
                incomplete = {**coverage, "target_statuses": [
                    {**item, "experiment_ids": (
                        item["experiment_ids"] if item["target_id"] == "wingate_peak_power" else []
                    )}
                    for item in target_statuses
                ]}
                workspace.save_research({"research_notes": ["single-layer attempt"]}, coverage=incomplete)
            saved = workspace.save_research(
                {"research_notes": ["all relevant layers covered"]}, coverage=coverage
            )
            self.assertEqual(len(saved["research_coverage"]["covered_model_layers"]), 5)

    def test_assess_targets_projects_latest_measurements_without_forecasting(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            initial = workspace.assess_targets(["cmj_height", "major_injury_count"])
            self.assertEqual(initial["counts"]["MEASUREMENT_REQUIRED"], 2)
            calculated = workspace.calculate_target(
                "major_injury_count", {"major_injury_count": 0}, units={"major_injury_count": "count"}
            )
            projected = workspace.assess_targets(["cmj_height", "major_injury_count"])
            by_id = {item["target_id"]: item for item in projected["targets"]}
            self.assertEqual(by_id["major_injury_count"]["status"], "TARGET_MET")
            self.assertEqual(by_id["major_injury_count"]["latest_calculation_id"], calculated["calculation_id"])
            self.assertEqual(by_id["cmj_height"]["required_inputs"], ["flight_time_s"])
            self.assertIn("no feasibility", projected["interpretation_boundary"])

    def test_measurement_portfolio_is_fault_isolated(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            result = workspace.calculate_targets([
                {"target_id": "major_injury_count", "inputs": {"major_injury_count": 0}, "units": {"major_injury_count": "count"}},
                {"target_id": "cmj_height"},
                {"target_id": "unknown_target"},
            ])
            self.assertEqual(result["counts"], {"CALCULATED": 1, "INPUT_REQUIRED": 1, "INVALID": 1})
            self.assertTrue(result["results"][0]["persisted"])
            self.assertFalse(result["results"][1]["persisted"])

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

    def test_ready_core_models_expose_typed_study_contracts(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "research.sqlite3") as workspace:
            for model_name in ("opensim", "pulse", "febio"):
                description = workspace.describe_model(model_name)
                self.assertEqual(description["research_readiness"], "TYPED_STUDY_CALLABLE")
                self.assertIn("research_input_schema", description)


if __name__ == "__main__":
    unittest.main()
