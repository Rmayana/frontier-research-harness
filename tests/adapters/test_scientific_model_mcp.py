from __future__ import annotations

import unittest

from frontier_research_harness.adapters.scientific_model_mcp import _list_tools
from frontier_research_harness.adapters.research_tool_contracts import list_tool_contracts
from frontier_research_harness.adapters.research_tool_dispatch import registered_research_tools


class ScientificModelMcpTests(unittest.IsolatedAsyncioTestCase):
    async def test_contract_catalog_and_dispatch_registry_stay_aligned(self):
        self.assertEqual(
            set(registered_research_tools()),
            {contract["name"] for contract in list_tool_contracts()},
        )

    async def test_mcp_uses_the_transport_independent_contract_catalog(self):
        mcp_tools = await _list_tools()
        self.assertEqual(
            [tool.model_dump(mode="json", by_alias=True, exclude_none=True) for tool in mcp_tools.tools],
            list_tool_contracts(),
        )

    async def test_public_surface_is_workspace_and_model_toolbox_only(self):
        result = await _list_tools()
        tools = result.tools
        names = {tool.name for tool in tools}
        self.assertEqual(
            names,
            {
                "inspect_environment",
                "research_log",
                "read_original_record",
                "search_retained",
                "load_research",
                "load_goal_map",
                "save_research",
                "list_knowledge_sources",
                "search_literature",
                "fetch_literature",
                "save_evidence",
                "save_footage_observation",
                "list_footage_observations",
                "compare_footage_observations",
                "load_evidence",
                "save_personal_observations",
                "list_personal_observations",
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
        self.assertTrue({"retained_claims", "applicability", "limitations"} <= set(evidence_required))
        evidence_schema = by_name["save_evidence"].input_schema["properties"]["record"]
        self.assertIn({"required": ["fetch_id"]}, evidence_schema["anyOf"])
        self.assertIn("oneOf", evidence_schema["properties"]["quality_appraisal"])
        self.assertIn("target_ids", evidence_required)
        self.assertIn(
            "evidence_passages",
            by_name["save_evidence"].input_schema["properties"]["record"]["properties"],
        )
        research_items = by_name["save_research"].input_schema["properties"]["data"]["properties"]["research_notes"]["items"]
        self.assertIn("oneOf", research_items)
        statement_item = research_items["oneOf"][1]
        self.assertEqual(
            set(statement_item["required"]),
            {"statement", "support_status"},
        )
        self.assertNotIn("minItems", statement_item["properties"]["target_ids"])
        self.assertNotIn("coverage", by_name["save_research"].input_schema["properties"])
        self.assertIn("max_utf8_bytes", by_name["load_research"].input_schema["properties"])
        self.assertEqual(
            by_name["load_research"].input_schema["properties"]["recent_items"]["default"],
            10,
        )
        self.assertEqual(
            by_name["load_research"].input_schema["properties"]["max_utf8_bytes"]["default"],
            32768,
        )
        self.assertIn("combat_task_ids", by_name["load_goal_map"].input_schema["properties"])
        self.assertIn("benchmark_ids", by_name["load_goal_map"].input_schema["properties"])
        self.assertIn(
            "research",
            by_name["load_research"].input_schema["properties"]["sections"]["items"]["enum"],
        )
        observation_items = by_name["save_personal_observations"].input_schema["properties"]["observations"]["items"]
        self.assertTrue(
            {"observed_at", "target_ids", "metric", "value", "unit", "protocol", "source_type", "provenance"}
            <= set(observation_items["required"])
        )
        self.assertNotIn("digital_twin", names)
        self.assertNotIn("simulation_lab", names)


if __name__ == "__main__":
    unittest.main()
