"""MCP transport adapter for the shared research Module Interface."""
from __future__ import annotations

import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from .research_tool_contracts import list_tool_contracts
from .research_tool_dispatch import dispatch_research_tool, tool_result_is_error


async def _list_tools(_context: Any = None, _params: Any = None) -> ListToolsResult:
    return ListToolsResult(tools=[Tool(**contract) for contract in list_tool_contracts()])


async def _call_tool(_context: Any, params: Any, *, database: Any = None) -> CallToolResult:
    result = dispatch_research_tool(params.name, params.arguments, database=database)
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(result, ensure_ascii=False))],
        isError=tool_result_is_error(result),
    )


server = Server(
    "frontier-science-model",
    on_list_tools=_list_tools,
    on_call_tool=_call_tool,
)


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
