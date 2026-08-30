from __future__ import annotations

import unittest

from frontier_research_harness.adapters.scientific_model_mcp import _list_tools


class ScientificModelMcpTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_surface_is_workspace_and_model_toolbox_only(self):
        result = await _list_tools()
        tools = result.tools
        names = {tool.name for tool in tools}
        self.assertEqual(
            names,
            {
                "load_research",
                "save_research",
                "list_knowledge_sources",
                "search_literature",
                "fetch_literature",
                "save_evidence",
                "save_footage_observation",
                "list_footage_observations",
                "compare_footage_observations",
                "load_evidence",
                "list_models",
                "describe_model",
                "run_model",
                "load_experiment",
                "list_experiments",
                "compare_runs",
                "calculate_target",
                "calculate_targets",
                "assess_targets",
                "load_calculation",
            },
        )
        serialized = str([tool.input_schema for tool in tools])
        for removed in ("expected_revision", "next_research_task", "proposal_id"):
            self.assertNotIn(removed, serialized)
        by_name = {tool.name: tool for tool in tools}
        search_schema = by_name["search_literature"].input_schema
        self.assertEqual(search_schema["required"], ["queries"])
        self.assertIn("queries", search_schema["properties"])
        self.assertIn("page_size", search_schema["properties"])
        self.assertNotIn("anyOf", search_schema)
        self.assertNotIn("searches", search_schema["properties"])
        classifications = by_name["save_evidence"].input_schema["properties"]["record"]["properties"]["classification"]["enum"]
        self.assertIn("EXTERNAL_RESEARCH", classifications)
        self.assertIn("EXTERNAL_PRIMARY_SOURCE", classifications)
        evidence_required = by_name["save_evidence"].input_schema["properties"]["record"]["required"]
        self.assertTrue({"title", "content_level", "retained_claims", "applicability", "limitations"} <= set(evidence_required))
        self.assertIn("coverage", by_name["save_research"].input_schema["properties"])
        self.assertIn("target_ids", by_name["list_models"].input_schema["properties"])
        self.assertEqual(
            set(by_name["run_model"].input_schema["required"]),
            {"name", "input", "question", "provenance"},
        )
        self.assertIn("max_utf8_bytes", by_name["load_research"].input_schema["properties"])
        self.assertIn(
            "research",
            by_name["load_research"].input_schema["properties"]["sections"]["items"]["enum"],
        )


if __name__ == "__main__":
    unittest.main()
