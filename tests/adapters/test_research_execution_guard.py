from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "plugins"
    / "frontier-science-model"
    / "hooks"
    / "research_execution_guard.py"
)
SPEC = importlib.util.spec_from_file_location("research_execution_guard", SCRIPT)
GUARD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(GUARD)


def post_event(tool: str, payload: dict, *, turn_id: str = "turn-1", tool_input: dict | None = None, error: bool = False) -> dict:
    return {
        "hook_event_name": "PostToolUse",
        "session_id": "session-1",
        "turn_id": turn_id,
        "tool_name": f"mcp__frontier-science-model__{tool}",
        "tool_input": tool_input or {},
        "tool_response": {
            "isError": error,
            "content": [{"type": "text", "text": json.dumps(payload)}],
        },
    }


def stop_event(*, turn_id: str = "turn-1", active: bool = False) -> dict:
    return {
        "hook_event_name": "Stop",
        "session_id": "session-1",
        "turn_id": turn_id,
        "stop_hook_active": active,
    }


class ResearchExecutionGuardTests(unittest.TestCase):
    def test_failed_tool_blocks_until_same_tool_succeeds(self):
        with tempfile.TemporaryDirectory() as root:
            failed = GUARD.handle(post_event("save_research", {}, error=True), root)
            self.assertEqual(failed["decision"], "block")
            GUARD.handle(post_event("save_research", {"saved": True}), root)
            self.assertEqual(GUARD.handle(stop_event(), root), {})

    def test_goal_research_requires_actual_model_run_and_validated_coverage(self):
        with tempfile.TemporaryDirectory() as root:
            GUARD.handle(post_event("load_research", {"workspace": {}}, tool_input={"sections": ["goal", "state"]}), root)
            GUARD.handle(post_event("search_literature", {"unique_result_count": 25, "failed_search_count": 0}, tool_input={"queries": [{"source": "pubmed", "query": "training"}]}), root)
            decision = GUARD.handle(stop_event(), root)
            self.assertEqual(decision["decision"], "block")
            self.assertIn("fetch and read", decision["reason"])
            self.assertIn("external-model catalog", decision["reason"])
            self.assertIn("successfully run", decision["reason"])
            self.assertIn("coverage receipt", decision["reason"])

            GUARD.handle(post_event("fetch_literature", {"content_level": "record_with_abstract"}, tool_input={"source": "pubmed", "identifier": "1"}), root)
            GUARD.handle(post_event("save_evidence", {"saved": True}), root)
            GUARD.handle(post_event("list_models", {"models": [{"execution_available": True}]}), root)
            GUARD.handle(post_event("save_research", {"saved": True}), root)
            still_incomplete = GUARD.handle(stop_event(), root)
            self.assertIn("successfully run", still_incomplete["reason"])
            self.assertIn("coverage receipt", still_incomplete["reason"])

            layers = {
                "pulse": "whole_person_physiology",
                "circadapt": "organ_circulation",
                "opensim": "musculoskeletal_mechanics",
                "febio": "tissue_durability",
                "mitocore": "cellular_metabolism",
            }
            for index, (model, layer) in enumerate(layers.items(), 1):
                GUARD.handle(post_event(
                    "run_model",
                    {"experiment_id": f"experiment-{index}", "research_layer": layer},
                    tool_input={
                        "name": model,
                        "question": "What boundary does the reference run establish?",
                        "provenance": [{"source": "model documentation"}],
                    },
                ), root)
            GUARD.handle(post_event(
                "save_research",
                {
                    "saved": True,
                    "research_coverage": {
                        "validated": True,
                        "scope": "whole_goal",
                        "target_count": 28,
                        "required_model_layers": list(layers.values()),
                        "covered_model_layers": list(layers.values()),
                    },
                },
                tool_input={
                    "coverage": {
                        "scope": "whole_goal",
                        "target_statuses": [{
                            "target_id": "vo2max",
                            "experiment_ids": [f"experiment-{index}" for index in range(1, 6)],
                        }],
                    }
                },
            ), root)
            self.assertEqual(GUARD.handle(stop_event(), root), {})

    def test_duplicate_fetch_is_reported_without_failing_the_turn(self):
        with tempfile.TemporaryDirectory() as root:
            event = post_event(
                "fetch_literature",
                {"content_level": "record_with_abstract"},
                tool_input={"source": "pubmed", "identifier": "123"},
            )
            self.assertEqual(GUARD.handle(event, root), {})
            duplicate = GUARD.handle(event, root)
            self.assertIn("already fetched", duplicate["hookSpecificOutput"]["additionalContext"])

    def test_current_model_run_must_be_attached_to_coverage(self):
        with tempfile.TemporaryDirectory() as root:
            GUARD.handle(post_event("load_research", {"workspace": {}}, tool_input={"sections": ["goal"]}), root)
            GUARD.handle(post_event("search_literature", {"unique_result_count": 0, "failed_search_count": 0}, tool_input={"queries": [{"source": "pubmed", "query": "target"}]}), root)
            GUARD.handle(post_event("list_models", {"models": [{"execution_available": True}]}), root)
            GUARD.handle(post_event(
                "run_model",
                {"experiment_id": "new-experiment", "research_layer": "organ_circulation"},
                tool_input={
                    "name": "circadapt",
                    "question": "What boundary does this establish?",
                    "provenance": [{"kind": "TEST"}],
                },
            ), root)
            GUARD.handle(post_event(
                "save_research",
                {"saved": True, "research_coverage": {"validated": True, "scope": "selected_targets", "target_count": 1, "required_model_layers": ["organ_circulation"], "covered_model_layers": ["organ_circulation"]}},
                tool_input={
                    "coverage": {
                        "scope": "selected_targets",
                        "target_statuses": [{"target_id": "vo2max", "experiment_ids": ["old-experiment"]}],
                    }
                },
            ), root)
            decision = GUARD.handle(stop_event(), root)
            self.assertIn("current-turn", decision["reason"])
            self.assertIn("organ_circulation", decision["reason"])

    def test_single_model_family_cannot_finish_multilayer_research(self):
        with tempfile.TemporaryDirectory() as root:
            GUARD.handle(post_event("load_research", {"workspace": {}}, tool_input={"sections": ["goal"]}), root)
            GUARD.handle(post_event("search_literature", {"unique_result_count": 0, "failed_search_count": 0}, tool_input={"queries": [{"source": "pubmed", "query": "whole goal"}]}), root)
            GUARD.handle(post_event("list_models", {"models": [{"execution_available": True}]}), root)
            GUARD.handle(post_event(
                "run_model",
                {"experiment_id": "mito-only", "research_layer": "cellular_metabolism"},
                tool_input={"name": "mitocore", "question": "What metabolic boundary applies?", "provenance": [{"kind": "TEST"}]},
            ), root)
            required = [
                "whole_person_physiology", "organ_circulation",
                "musculoskeletal_mechanics", "tissue_durability",
                "cellular_metabolism",
            ]
            GUARD.handle(post_event(
                "save_research",
                {"saved": True, "research_coverage": {"validated": True, "scope": "whole_goal", "target_count": 28, "required_model_layers": required, "covered_model_layers": required}},
                tool_input={"coverage": {"scope": "whole_goal", "target_statuses": [{"target_id": "wingate_peak_power", "experiment_ids": ["mito-only"]}]}},
            ), root)
            decision = GUARD.handle(stop_event(), root)
            self.assertIn("whole_person_physiology", decision["reason"])
            self.assertIn("musculoskeletal_mechanics", decision["reason"])

    def test_stop_continuation_is_bounded(self):
        with tempfile.TemporaryDirectory() as root:
            GUARD.handle(post_event("search_literature", {"unique_result_count": 3}), root)
            self.assertEqual(GUARD.handle(stop_event(), root)["decision"], "block")
            self.assertEqual(GUARD.handle(stop_event(active=True), root), {})
            self.assertEqual(GUARD.handle(stop_event(), root), {})

    def test_technical_footage_only_research_does_not_require_a_model(self):
        with tempfile.TemporaryDirectory() as root:
            GUARD.handle(post_event("load_research", {"workspace": {}}, tool_input={"sections": ["goal"]}), root)
            GUARD.handle(post_event("search_literature", {"unique_result_count": 1, "failed_search_count": 0}, tool_input={"queries": [{"source": "nsca", "query": "Beterbiev footage"}]}), root)
            GUARD.handle(post_event("fetch_literature", {"content_level": "primary_source_observation"}, tool_input={"source": "nsca", "identifier": "video-1"}), root)
            GUARD.handle(post_event("save_evidence", {"saved": True}, tool_input={"record": {"classification": "EXTERNAL_PRIMARY_SOURCE", "content_level": "primary_source_observation", "retained_claims": ["timestamped observation"]}}), root)
            GUARD.handle(post_event(
                "save_research",
                {"saved": True, "research_coverage": {"validated": True, "scope": "selected_targets", "target_count": 1}},
                tool_input={"coverage": {"scope": "selected_targets", "requested_target_ids": ["technical_goal"], "target_statuses": [{"target_id": "technical_goal", "experiment_ids": []}]}},
            ), root)
            self.assertEqual(GUARD.handle(stop_event(), root), {})


if __name__ == "__main__":
    unittest.main()
