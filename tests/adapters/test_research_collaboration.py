from __future__ import annotations

import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

from frontier_research_harness.adapters.frontier_science_workspace import FrontierScienceWorkspace
from frontier_research_harness.adapters.scientific_model_mcp import _call_tool, _list_tools
from frontier_research_harness.research_contracts import ResearchEntry


class ResearchCollaborationTests(unittest.TestCase):
    def test_parallel_synthesis_conflict_keeps_history_and_contributions(self):
        with tempfile.TemporaryDirectory() as root:
            db = Path(root) / "research.db"
            with FrontierScienceWorkspace(db) as a, FrontierScienceWorkspace(db) as b:
                revision = a.load_research()["updated_at"]
                a.research_log("append", {"author": "CODEX", "agent_id": "branch-a", "text": "Hypothesis A"})
                b.research_log("append", {"author": "CODEX", "agent_id": "branch-b", "text": "Contradictory assumption B"})
                a.save_research({"current_understanding": "A under assumption X"}, expected_updated_at=revision)
                with self.assertRaisesRegex(RuntimeError, "stale research synthesis"):
                    asyncio.run(_call_tool(None, SimpleNamespace(name="save_research", arguments={"data": {"current_understanding": "B"}, "expected_updated_at": revision}), database=db))
                current = b.load_research()
                self.assertEqual(current["workspace"]["current_understanding"], "A under assumption X")
                b.save_research({"current_understanding": "A and B differ by X; test X"}, expected_updated_at=current["updated_at"])
                history = b.connection.execute("SELECT text FROM frontier_science_understanding_history").fetchall()
                self.assertNotIn("B", [row[0] for row in history])
                self.assertEqual(len(b.research_log("list", {})["entries"]), 2)

    def test_original_unicode_pages_and_find_cover_exact_bytes(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "r.db") as w:
            raw = json.dumps({"methods": ('한글🙂 "quoted"\n' * 450), "result": "different mechanism"}, ensure_ascii=False)
            w.connection.execute("INSERT INTO frontier_science_fetches VALUES(?,?,?)", ("f", "2026", raw)); w.connection.commit()
            offset, parts, digest = 0, [], None
            while True:
                page = w.read_original_record("literature_fetch", "f", byte_offset=offset, max_utf8_bytes=1024, expected_sha256=digest)
                self.assertLessEqual(len(json.dumps(page, ensure_ascii=False).encode()), 1024)
                parts.append(page["content"]); digest = page["content_sha256"]
                if page["next_byte_offset"] is None: break
                self.assertGreater(page["next_byte_offset"], offset)
                offset = page["next_byte_offset"]
            self.assertEqual("".join(parts), raw)
            page = w.read_original_record("literature_fetch", "f", find_text="different mechanism")
            self.assertTrue(page["found"]); self.assertTrue(page["content"].startswith("different mechanism"))
            self.assertFalse(w.read_original_record("literature_fetch", "f", find_text="absent")["found"])
            with self.assertRaisesRegex(ValueError, "hash"):
                w.read_original_record("literature_fetch", "f", expected_sha256="wrong")
            with self.assertRaisesRegex(ValueError, "UTF-8"):
                w.read_original_record("literature_fetch", "f", byte_offset=raw.encode().index("한".encode()) + 1)
            with self.assertRaisesRegex(ValueError, "exceeds"):
                w.read_original_record("literature_fetch", "f", byte_offset=len(raw.encode()) + 1)

    def test_retained_pages_freeze_range_and_share_cli_surface(self):
        with tempfile.TemporaryDirectory() as root:
            db = Path(root) / "r.db"
            with FrontierScienceWorkspace(db) as w:
                for i in range(3):
                    w.research_log("append", {"author": "CODEX", "agent_id": f"a{i}", "text": f"mechanism {i}"})
                first = w.search_retained("mechanism", "research_entry", limit=1)
                w.research_log("append", {"author": "USER", "text": "mechanism new"})
                second = w.search_retained("mechanism", "research_entry", limit=10, after_rowid=first["next_after_rowid"], through_rowid=first["through_rowid"])
                self.assertEqual(len(second["matches"]), 2)
                locator = second["matches"][0]["reload"]
                entry = w.research_log(**locator["arguments"])["entries"][0]
                self.assertEqual(entry["entry_id"], second["matches"][0]["record_id"])
            result = subprocess.run([sys.executable, "-m", "frontier_research_harness.adapters.research_cli", "search_retained", "--database", str(db)],
                input=json.dumps({"query": "mechanism", "record_type": "research_entry"}), text=True, encoding="utf-8", capture_output=True, check=True)
            self.assertIn("mechanism", result.stdout)
            names = {tool.name for tool in asyncio.run(_list_tools()).tools}
            self.assertTrue({"read_original_record", "search_retained"} <= names)

    def test_agent_cannot_be_recorded_as_human(self):
        with self.assertRaises(ValueError): ResearchEntry(author="USER", agent_id="branch", text="approved")


if __name__ == "__main__": unittest.main()
