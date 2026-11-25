"""Single-user stdio MCP. Network reads and local record operations are separate tools."""
import json
from typing import Any

from mcp.server.fastmcp import FastMCP, Image
from mcp.types import ToolAnnotations

from training_analysis import inspect_video as inspect_media, read_activity, run_analysis
from training_literature import read_source, search_papers
from training_records import append_record, read_record

server = FastMCP("frontier-training")


def inspect_video(filename: str, seconds: float | None = None) -> list[Any]:
    """Inspect an inbox video. Request seconds to return one frame for visual analysis."""
    result = dict(inspect_media(filename, seconds))
    frame = result.pop("frame_jpeg", None)
    content = [json.dumps(result, ensure_ascii=False)]
    if frame is not None:
        content.append(Image(data=frame, format="jpeg"))
    return content


for function in (search_papers, read_source, inspect_video, read_activity, run_analysis, read_record, append_record):
    server.add_tool(function, annotations=ToolAnnotations(
        readOnlyHint=function is not append_record,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=function in (search_papers, read_source),
    ), structured_output=False if function is inspect_video else None)


if __name__ == "__main__":
    server.run(transport="stdio")
