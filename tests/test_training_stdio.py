"""Exercise the same Windows stdio launcher registered in the project config."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import tomllib
import unittest
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
LAUNCH = tomllib.loads((ROOT / ".codex/config.toml").read_text("utf-8"))["mcp_servers"]["frontier-training"]


@asynccontextmanager
async def connect(config):
    params = StdioServerParameters(command=LAUNCH["command"], args=LAUNCH["args"], cwd=ROOT,
                                   env={"FRONTIER_TRAINING_CONFIG": str(config)})
    async with stdio_client(params) as (reader, writer), ClientSession(reader, writer) as client:
        await client.initialize()
        yield client


async def call(client, tool, args):
    result = await client.call_tool(tool, args)
    if result.isError:
        raise AssertionError(result.content)
    return json.loads(result.content[0].text)


class TrainingStdioTest(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "The deployed launcher runs on Windows")
    def test_resume_across_server_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            config = temp / "runtime.json"
            config.write_text(json.dumps({"records": str(temp)}), encoding="utf-8")
            (temp / "inbox").mkdir()
            (temp / "inbox" / "activity.csv").write_text("score\n7\n8\n", encoding="utf-8")
            asyncio.run(self.round_trip(config))

    async def round_trip(self, config):
        async with connect(config) as first:
            tools = {t.name for t in (await first.list_tools()).tools}
            self.assertEqual(tools, {"search_papers", "read_source", "inspect_video", "read_activity",
                                     "run_analysis", "append_record", "read_record"})
            prediction = await call(first, "append_record", {
                "topic": "합성 리듬", "kind": "prediction", "body": "8점 이상 예상", "request_id": "p1"})
            actual = await call(first, "append_record", {"topic": "합성 리듬", "kind": "actual",
                               "body": "7점, 8점", "request_id": "a1", "refs": [prediction["id"]]})
        async with connect(config) as second:
            records = (await call(second, "read_record", {"topic": "합성 리듬"}))["records"]
            self.assertEqual(records[0]["id"], actual["id"])
            self.assertEqual(records[1]["body"], "8점 이상 예상")
            page = await call(second, "read_activity", {"filename": "activity.csv"})
            scores = [float(r["score"]) for r in page["rows"]]
            result = await call(second, "run_analysis", {
                "baseline": [6, 7], "followup": scores, "paired": True, "unit": "점"})
            self.assertEqual(result["mean_change"], 1)
            self.assertEqual(result["unit"], "점")
