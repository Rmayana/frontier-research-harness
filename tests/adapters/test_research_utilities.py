from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from frontier_research_harness.adapters.frontier_science_workspace import FrontierScienceWorkspace
from frontier_research_harness.evidence_navigation import literature_navigation




class ResearchUtilitiesTests(unittest.TestCase):



    def test_joint_notes_and_revised_explanation_do_not_activate(self):
        with tempfile.TemporaryDirectory() as root:
            db = Path(root)/"r.db"
            with FrontierScienceWorkspace(db) as w:
                user = w.research_log("append", {"author": "USER", "text": "Could coordination explain this?"})
                answer = w.research_log("append", {"author": "CODEX", "text": "Alternative explanation; compare controls.", "in_reply_to": user["entry_id"], "label": "working interpretation"})
                self.assertFalse(answer["activation"])
                self.assertEqual(answer["verification"], "UNASSESSED_NOTE")
                with self.assertRaises(ValueError):
                    w.research_log("append", {"author": "CODEX", "text": "x", "in_reply_to": "missing"})
            with FrontierScienceWorkspace(db) as w:
                page = w.research_log("list", {"limit": 1})
                self.assertTrue(page["more_available"])
                next_page = w.research_log("list", {"after_sequence": page["next_after_sequence"]})
                self.assertEqual(next_page["entries"][0]["record"]["in_reply_to"], user["entry_id"])


    def test_cli_uses_same_surface_and_reports_errors(self):
        with tempfile.TemporaryDirectory() as root:
            cmd = [sys.executable, "-X", "utf8", "-m", "frontier_research_harness.adapters.research_cli"]
            result = subprocess.run([*cmd, "research_log", "--database", str(Path(root)/"r.db")], input=json.dumps({"operation": "append", "payload": {"author": "USER", "text": "공동 연구"}}), text=True, encoding="utf8", capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["record"]["text"], "공동 연구")
            failed = subprocess.run([*cmd, "unknown", "--database", str(Path(root)/"r.db")], input="{}", text=True, capture_output=True)
            self.assertEqual(failed.returncode, 1)
            self.assertEqual(json.loads(failed.stdout)["status"], "FAILED")

    def test_navigation_does_not_claim_linked_content_was_read(self):
        result = literature_navigation({"raw": '<article xmlns:xlink="http://www.w3.org/1999/xlink"><sec id="s1"><title>Methods</title><supplementary-material xlink:href="supp.csv"/></sec><ref id="r1"><pub-id pub-id-type="doi">10.example/x</pub-id></ref></article>'})
        self.assertEqual(result["references"][0]["identifiers"][0]["id"], "10.example/x")
        self.assertEqual(result["linked_material"][0]["href"], "supp.csv")
        self.assertIn("NOT been fetched", result["note"])
