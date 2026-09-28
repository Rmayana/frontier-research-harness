from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

from frontier_research_harness.external_models.core_experiment_contracts import CalibrationBoundary, OpenSimReactionSeriesStudy
from frontier_research_harness.external_models.core_output_normalizers import normalize_opensim
from tests.external_models.test_core_output_normalizers import receipt


def series():
    return {"observable_kind": "JOINT_REACTION_SERIES", "joint": "joint", "side": "child", "expressed_in_frame": "ground",
            "samples": [{"time_seconds": t, "force_n": [0, f, 0], "moment_nm": [0, 0, 2]}
                        for t, f in [(0, 2), (.5, 4), (2, 10)]]}


class OpenSimSeriesTests(unittest.TestCase):
    def test_nonuniform_time_integral_and_mean(self):
        result = normalize_opensim(receipt(stdout=json.dumps(series())))
        self.assertEqual(result["force_magnitude_integral_ns"], 12)
        self.assertEqual(result["time_mean_force_n"], 6)
        self.assertEqual(result["peak_force_n"], 10)
        self.assertIn("not vector impulse", result["aggregation"])

    def test_rejects_invalid_time_vectors_and_nonfinite_values(self):
        for field, value in [("time_seconds", 0), ("force_n", [1, 2]),
                             ("force_n", [1, float("nan"), 0]), ("force_n", [True, 0, 0])]:
            with self.subTest(field=field, value=value):
                payload = series()
                payload["samples"][1][field] = value
                with self.assertRaises(ValueError):
                    normalize_opensim(receipt(stdout=json.dumps(payload)))

    def test_job_declares_driver_model_and_states_for_preservation(self):
        study = OpenSimReactionSeriesStudy(model_path="models/body.osim", states_path="studies/states.json",
                                          joint="knee", side="child", calibration=CalibrationBoundary.REFERENCE)
        job = study.to_job()
        self.assertEqual(len(job.input_artifacts), 3)
        self.assertIn("studies/states.json", job.arguments)
        with self.assertRaises(ValueError):
            OpenSimReactionSeriesStudy(**{**study.model_dump(), "states_path": "../escape.json"})

    def test_driver_rejects_ambiguous_default_and_missing_times(self):
        path = Path(__file__).resolve().parents[2] / "scripts/external_engines/opensim_reaction_series.py"
        spec = importlib.util.spec_from_file_location("series_driver", path)
        driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(driver)
        valid = {"snapshots": [{"time_seconds": t, "state_variable_values": {}} for t in (0, 1)]}
        self.assertFalse(driver.validate_series(valid)[1])
        for change in ({"allow_model_defaults": "false"}, {"snapshots": [{"time_seconds": 0}]},
                       {"unknown": True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                driver.validate_series({**valid, **change})


if __name__ == "__main__":
    unittest.main()
