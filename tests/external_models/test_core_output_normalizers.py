from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from frontier_research_harness.external_models.core_output_normalizers import (
    normalize_febio,
    normalize_opensim,
    normalize_pulse,
)
from frontier_research_harness.external_models.external_engine_runner import (
    ArtifactReceipt,
    ExternalEngineReceipt,
)


def artifact(path: Path) -> ArtifactReceipt:
    payload = path.read_bytes()
    return ArtifactReceipt(path=str(path), sha256=hashlib.sha256(payload).hexdigest(), size_bytes=len(payload))


def receipt(*, stdout: str = "", outputs: tuple[ArtifactReceipt, ...] = ()) -> ExternalEngineReceipt:
    return ExternalEngineReceipt(
        component_id="test", runtime_path="test-runtime", arguments=(), exit_code=0,
        stdout=stdout, stderr="", inputs=(), outputs=outputs,
    )


class CoreOutputNormalizerTests(unittest.TestCase):
    def test_opensim_exposes_vector_magnitudes_without_endpoint_claim(self):
        raw = json.dumps({
            "joint": "knee_r", "side": "child", "time_seconds": 1.0,
            "force_n": [3, 4, 0], "moment_nm": [0, 0, 2],
            "state_kind": "CALLER_SPECIFIED_STATE_SNAPSHOT",
            "applied_state_variable_values": {"knee_angle": 0.5},
        })
        normalized = normalize_opensim(receipt(stdout=raw))
        self.assertEqual(normalized["force_magnitude_n"], 5.0)
        self.assertIn("not CMJ performance", normalized["limitations"][0])

    def test_pulse_summarizes_finite_values_and_declared_hrr(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "results.csv"
            path.write_text(
                "Time(s),HeartRate(1/min),OxygenConsumptionRate(mL/min),TotalMetabolicRate(W),AchievedExerciseLevel\n"
                "0,70,250,80,0\n60,160,3000,500,1\n120,110,1000,200,0\n",
                encoding="utf-8",
            )
            normalized = normalize_pulse(receipt(outputs=(artifact(path),)), exercise_end_seconds=60)
        self.assertEqual(normalized["heart_rate_recovery"]["decrease_bpm"], 50.0)
        self.assertEqual(normalized["columns"]["oxygen_consumption_ml_min"]["maximum"], 3000.0)

    def test_febio_reports_solver_status_but_not_damage(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "model.log"
            path.write_text(
                "converged at time : 1\nNumber of time steps completed : 10\n"
                "N O R M A L   T E R M I N A T I O N\n", encoding="utf-8",
            )
            normalized = normalize_febio(receipt(outputs=(artifact(path),)))
        self.assertTrue(normalized["normal_termination"])
        self.assertEqual(normalized["completed_time_steps"], 10)
        self.assertIn("not anatomical validation", normalized["limitations"][0])

    def test_recovery_requires_the_actual_later_sample(self):
        for times, reason in (("0,120\n60,100\n", "OUTSIDE_RECORDED_HORIZON"),
                              ("0,120\n60,100\n180,70\n", "REQUESTED_SAMPLE_NOT_PRESENT")):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as root:
                path = Path(root) / "results.csv"
                path.write_text("Time(s),HeartRate(1/min)\n" + times, encoding="utf-8")
                result = normalize_pulse(receipt(outputs=(artifact(path),)), exercise_end_seconds=60)
                self.assertIsNone(result["heart_rate_recovery"])
                self.assertEqual(result["heart_rate_recovery_status"], reason)

    def test_recovery_rejects_invalid_interval_and_unordered_samples(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            normalize_pulse(receipt(), recovery_interval_seconds=0)
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "results.csv"
            path.write_text("Time(s),HeartRate(1/min)\n60,100\n0,70\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "increasing"):
                normalize_pulse(receipt(outputs=(artifact(path),)), exercise_end_seconds=0)


if __name__ == "__main__":
    unittest.main()
