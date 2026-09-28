from __future__ import annotations

import asyncio
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from frontier_research_harness.adapters.frontier_science_workspace import FrontierScienceWorkspace
from frontier_research_harness.adapters.scientific_model_mcp import _call_tool
from frontier_research_harness.external_models.external_engine_runner import ExternalEngineError, ExternalEngineFailure
from tests.adapters.test_frontier_science_workspace import scholarly_evidence


class ResearchContinuityTests(unittest.TestCase):
    def test_understanding_revises_and_survives_reopen_without_erasing_notes(self):
        with tempfile.TemporaryDirectory() as root:
            database = Path(root) / "research.sqlite3"
            with FrontierScienceWorkspace(database) as workspace:
                workspace.save_research({"current_understanding": "A explains the observation.", "research_notes": ["Original observation"]})
                workspace.save_research({"current_understanding": "B better explains the contrary result."})
                workspace.save_research({"current_understanding": "B better explains the contrary result."})
            with FrontierScienceWorkspace(database) as workspace:
                loaded = workspace.load_research(sections=["current_understanding", "research_notes"], history_limit=10)["workspace"]
                self.assertEqual(loaded["current_understanding"], "B better explains the contrary result.")
                self.assertEqual(loaded["research_notes"], ["Original observation"])
                self.assertEqual([item["text"] for item in loaded["understanding_history"]], [
                    "B better explains the contrary result.", "A explains the observation.",
                ])
                workspace.save_research({"current_understanding": ""})
                self.assertEqual(len(workspace.load_research(history_limit=10)["workspace"]["understanding_history"]), 3)

    def test_history_respects_context_budget(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "r.sqlite3") as workspace:
            workspace.save_research({"current_understanding": "가" * 3000})
            workspace.save_research({"current_understanding": "Revised."})
            result = workspace.load_research(sections=["current_understanding"], history_limit=2, max_utf8_bytes=4096)
            self.assertEqual(result["workspace"]["current_understanding"], "Revised.")
            self.assertIn("understanding_history", result["omitted_sections"])
            self.assertLessEqual(len(json.dumps(result, ensure_ascii=False).encode()), 4096)

    def test_fetch_receipt_reuses_exact_payload_after_reopen(self):
        evidence = scholarly_evidence()
        fetched = {**evidence["fetched_record"], "url": evidence["reference_url"]}
        with tempfile.TemporaryDirectory() as root:
            database = Path(root) / "r.sqlite3"
            with FrontierScienceWorkspace(database) as workspace, patch(
                "frontier_research_harness.adapters._workspace_evidence.ScientificKnowledgeClient"
            ) as client:
                workspace.save_research({'fixed_goal': {'physical_targets': [{'id': 'vo2max'}]}}, fixed_goal_change_approved=True)
                client.return_value.fetch.return_value = fetched
                fetch_id = workspace.fetch_literature("pubmed", "123")["fetch_id"]
                self.assertEqual(workspace.load_research()["evidence_count"], 0)
            with FrontierScienceWorkspace(database) as workspace:
                compact = {key: evidence[key] for key in (
                    "retained_claims", "applicability", "limitations", "target_ids", "evidence_passages"
                )}
                compact.update(fetch_id=fetch_id, quality_appraisal="Synthetic abstract only; no personal response claim.")
                saved = workspace.save_evidence(compact)
                retained = workspace.load_evidence(saved["evidence_id"])["record"]
                self.assertEqual(retained["fetched_record"], fetched)
                self.assertEqual(retained["title"], fetched["title"])
                self.assertEqual(retained["quality_appraisal"]["narrative"], compact["quality_appraisal"])
                self.assertTrue(workspace.save_evidence(compact)["deduplicated"])
                with self.assertRaisesRegex(ValueError, "conflicts"):
                    workspace.save_evidence({**compact, "content_level": "full_text"})
                with self.assertRaisesRegex(ValueError, "unknown literature fetch_id"):
                    workspace.save_evidence({**compact, "fetch_id": "missing"})

    def test_cached_metadata_does_not_become_read_evidence(self):
        with tempfile.TemporaryDirectory() as root, FrontierScienceWorkspace(Path(root) / "r.sqlite3") as workspace, patch(
            "frontier_research_harness.adapters._workspace_evidence.ScientificKnowledgeClient"
        ) as client:
            client.return_value.fetch.return_value = {
                "source": "crossref", "identifier": "10.test/1", "url": "https://example.test/1",
                "title": "Metadata", "content_level": "metadata_only", "raw": {"title": ["Metadata"]},
            }
            fetched = workspace.fetch_literature("crossref", "10.test/1")
            with self.assertRaises(ValueError):
                workspace.save_evidence({
                    "fetch_id": fetched["fetch_id"], "retained_claims": ["Unsupported"],
                    "applicability": "Test", "limitations": ["Metadata only"], "target_ids": ["vo2max"],
                })


    def test_existing_database_receipts_are_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            database = Path(root) / "r.sqlite3"
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.execute("CREATE TABLE frontier_science_experiments (experiment_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, question TEXT, model_name TEXT NOT NULL, model_version TEXT NOT NULL, input_hash TEXT NOT NULL, input_json TEXT NOT NULL, output_json TEXT NOT NULL, interpretation TEXT, provenance_json TEXT NOT NULL)")
                connection.execute("INSERT INTO frontier_science_experiments VALUES ('old','2026-01-01','q','pulse','v1','hash','{}','{}',NULL,'[]')")
            with FrontierScienceWorkspace(database) as workspace:
                self.assertEqual(workspace.load_experiment("old")["status"], "SUCCEEDED")
                self.assertEqual(workspace.load_research(sections=["current_understanding"])["workspace"]["current_understanding"], "")
