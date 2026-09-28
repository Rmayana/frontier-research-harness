from __future__ import annotations

import json
import unittest
from pathlib import Path

from frontier_research_harness.goal_structure import (
    expand_goal_research_map,
    load_goal_research_map,
    validate_goal_research_map,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class GoalResearchMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.goal = json.loads((PROJECT_ROOT / "tests/fixtures/legacy-detailed-goal.json").read_text(encoding="utf-8"))
        self.structure = load_goal_research_map(self.goal, project_root=PROJECT_ROOT)

    def test_map_covers_detailed_success_targets_and_quantitative_subtargets(self):
        validation = validate_goal_research_map(self.goal, self.structure)
        self.assertTrue(validation["validated"])
        self.assertEqual(validation["physical_target_count"], 7)
        self.assertEqual(validation["quantitative_subtarget_count"], 27)
        self.assertEqual(validation["capacity_count"], 7)
        self.assertEqual(self.goal["revision"], 3)
        self.assertEqual(
            self.goal["performance_context"]["whole_person_combat_capability_target"],
            "human limit",
        )
        self.assertIn("전투력을 인간 한계치까지", self.goal["north_star"])
        self.assertEqual(
            self.structure.whole_person_views[0].id,
            "human_limit_integrated_combat_capability",
        )
        self.assertEqual(self.goal["physical_targets"][0]["id"], "force_production")
        self.assertEqual(self.goal["measurement_benchmarks"][0]["target"], "60–70 N/kg")
        self.assertEqual(
            self.structure.relationship_status,
            "RESEARCH_ROUTING_HYPOTHESES",
        )

    def test_combat_task_expansion_keeps_actions_and_observations_separate(self):
        expanded = expand_goal_research_map(
            self.structure,
            combat_task_ids=["round_output_management"],
        )
        self.assertEqual(expanded["mode"], "connected_subgraph")
        self.assertTrue(expanded["capacity_nodes"])
        self.assertTrue(expanded["diagnostic_nodes"])
        self.assertTrue(expanded["intervention_nodes"])
        self.assertTrue(expanded["benchmark_observations"])
        self.assertTrue(all(
            item["approval_required_before_activation"]
            for item in expanded["intervention_nodes"]
        ))
        self.assertNotIn("strategy", expanded)


if __name__ == "__main__":
    unittest.main()
