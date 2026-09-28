from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from frontier_research_harness.adapters.frontier_science_workspace import FrontierScienceWorkspace


class ResearchTransparencyTests(unittest.TestCase):
    def test_full_text_search_finds_case_variants_and_keeps_snapshot_cursor(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "test.sqlite3") as workspace:
            def insert(identifier, text):
                workspace.connection.execute("INSERT INTO frontier_science_fetches VALUES(?,?,?)",
                                             (identifier, "2026-01-01", json.dumps({"text": text})))
                workspace.connection.commit()
            insert("first", "FORCE and tendon stiffness")
            insert("second", "force responds to stiffness")
            result = workspace.search_retained("force stiffness", "literature_fetch", mode="full_text", limit=1)
            self.assertEqual(result["matches"][0]["record_id"], "first")
            insert("late", "force stiffness")
            next_page = workspace.search_retained("force stiffness", "literature_fetch", mode="full_text",
                after_rowid=result["next_after_rowid"], through_rowid=result["through_rowid"])
            self.assertEqual([x["record_id"] for x in next_page["matches"]], ["second"])
            self.assertEqual(len(workspace.search_retained("force stiffness", "literature_fetch", mode="full_text")["matches"]), 3)
            self.assertEqual(workspace.search_retained("force and tendon", "literature_fetch")["matches"], [])

    def test_large_understanding_has_an_exact_recoverable_revision(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "test.sqlite3") as workspace:
            text = "새 근거로 바뀐 설명과 미해결 가정. " * 1000
            workspace.save_research({"current_understanding": text})
            loaded = workspace.load_research(sections=["current_understanding"], max_utf8_bytes=4096)
            self.assertTrue(loaded["workspace"]["current_understanding"])
            self.assertIn("current_understanding", loaded["truncated_sections"])
            self.assertLessEqual(len(json.dumps(loaded, ensure_ascii=False).encode()), 4096)
            arguments = loaded["section_continuations"]["current_understanding"]["arguments"]
            pieces, digest = [], None
            while True:
                page = workspace.read_original_record(**arguments, expected_sha256=digest)
                pieces.append(page["content"])
                digest = page["content_sha256"]
                if page["next_byte_offset"] is None:
                    break
                arguments["byte_offset"] = page["next_byte_offset"]
            self.assertEqual(json.loads("".join(pieces))["text"], text)


if __name__ == "__main__":
    unittest.main()
