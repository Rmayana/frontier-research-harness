"""Live integration checks, not a scientific experiment or research workflow."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from frontier_research_harness.adapters.frontier_science_workspace import FrontierScienceWorkspace
from frontier_research_harness.adapters.scientific_knowledge import ScientificKnowledgeClient


async def check_mcp() -> dict:
    settings = json.loads(Path("plugins/frontier-science-model/.mcp.json").read_text(encoding="utf8"))
    server = settings["mcpServers"]["frontier-science-model"]
    async with stdio_client(StdioServerParameters(**server)) as streams:
        async with ClientSession(*streams, read_timeout_seconds=30) as session:
            await session.initialize()
            names = {t.name for t in (await session.list_tools()).tools}
            assert {"research_log", "inspect_environment"} <= names
            result = await session.call_tool("list_knowledge_sources", {})
            assert not result.is_error
            return {"transport": "stdio", "tool_count": len(names), "call_succeeded": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--mcp", action="store_true")
    args = parser.parse_args()
    destination = Path(".scratch/research-lab-acceptance")
    destination.mkdir(parents=True, exist_ok=True)
    report = {"classification": "ENGINEERING_ACCEPTANCE_NOT_PERSONAL_RESEARCH"}
    with FrontierScienceWorkspace(destination / "acceptance.sqlite3") as w:
        if args.online:
            search = w.search_literature_portfolio([
                {"source": "pubmed", "query": "39169839[uid]"},
                {"source": "europe_pmc", "query": "EXT_ID:39169839"},
            ], limit_per_search=2)
            report["search"] = search
            assert search["unique_result_count"] > 0, search
            fetched = w.fetch_literature("pubmed", "39169839")
            report["fetch"] = {k: fetched.get(k) for k in ("fetch_id", "content_level", "has_full_text", "navigation")}
            assert fetched["raw"]
            # A non-OA abstract fallback is valid, but does not test full-text navigation.
            candidate = ScientificKnowledgeClient().search("europe_pmc", "PMCID:PMC6084043", limit=1)
            full = w.fetch_literature("pubmed", candidate["results"][0]["id"])
            report["open_access_fetch"] = {k: full.get(k) for k in ("fetch_id", "content_level", "has_full_text", "navigation")}
            assert full["content_level"] == "full_text", full.get("full_text_resolution")
            assert full["navigation"]["counts"]["references"] > 0
        if args.mcp:
            report["mcp"] = asyncio.run(check_mcp())
    (destination / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf8")
    print(json.dumps(report, ensure_ascii=False))



if __name__ == "__main__":
    main()
