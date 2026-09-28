"""Ensure research tools stay independent of experiment execution and registration."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from adapters.legacy_records import seed_experiment
from frontier_research_harness.adapters.frontier_science_workspace import FrontierScienceWorkspace
from frontier_research_harness.adapters.research_tool_contracts import list_tool_contracts
from frontier_research_harness.adapters.research_tool_dispatch import dispatch_research_tool


class DirectModelBoundaryTests(unittest.TestCase):
    def test_no_simulator_calculator_or_registration_tool_remains(self):
        names = {t["name"] for t in list_tool_contracts()}
        removed = {"run_model", "describe_model", "list_models", "compare_runs", "load_experiment", "list_experiments",
                   "simulation_lab", "digital_twin", "numerical_workbench", "dataset", "reference_data", "archived_simulation"}
        self.assertFalse(names & removed)
        self.assertFalse(hasattr(FrontierScienceWorkspace, "run_model"))
        self.assertFalse(hasattr(FrontierScienceWorkspace, "calculate_target"))
        for name in removed:
            with self.assertRaisesRegex(ValueError, "unknown tool"):
                dispatch_research_tool(name)

    def test_research_import_does_not_load_removed_experiment_layers(self):
        script = '''import sys
from frontier_research_harness.adapters.research_tool_contracts import list_tool_contracts
from frontier_research_harness.adapters.frontier_science_workspace import FrontierScienceWorkspace
list_tool_contracts()
removed = ('numerical_workbench', 'dataset_fitting', 'population_reference', 'target_calculator', 'model_capabilities')
assert not any('frontier_research_harness.' + name in sys.modules for name in removed)
'''
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_historical_experiment_has_complete_bounded_reload_locator(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "history.db"
            with FrontierScienceWorkspace(db) as w:
                original = seed_experiment(w, model_input={"mass": 2}, raw_output={"force": 27.62})
                event = next(e for e in w.load_research()["workspace"]["recent_activity"]["events"]
                             if e["id"] == original["experiment_id"])
            loaded = dispatch_research_tool(event["reload"]["tool"], event["reload"]["arguments"], database=db)
            exact = json.loads(loaded["content"])
            self.assertEqual(exact["input"], {"mass": 2})
            self.assertEqual(exact["raw_output"], {"force": 27.62})
            self.assertTrue(exact["provenance"])

    def test_old_simulator_json_remains_readable_without_archive_runtime(self):
        with tempfile.TemporaryDirectory() as folder, FrontierScienceWorkspace(Path(folder)/"history.db") as w:
            w.connection.execute("CREATE TABLE frontier_science_twin_runs (projection_id TEXT,record_json TEXT)")
            original = {"input": {"x": 1}, "raw": {"y": 2}, "limitations": ["old conditional result"]}
            w.connection.execute("INSERT INTO frontier_science_twin_runs VALUES(?,?)", ("old", json.dumps(original)))
            w.connection.commit()
            before = w.connection.total_changes
            result = w.read_original_record("projection", "old")
            self.assertEqual(json.loads(result["content"]), original)
            self.assertEqual(w.connection.total_changes, before)
            self.assertIn("Retrieval is not verification", result["read_boundary"])
