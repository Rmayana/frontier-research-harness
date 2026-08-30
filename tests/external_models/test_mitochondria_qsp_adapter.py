"""Tests for the passive mitochondrial QSP adapter."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from frontier_research_harness.external_models.mitochondria_qsp_adapter import (
    IndexedValue,
    MitoQspCondition,
    MitoQspExperimentRequest,
    MitochondriaQspPassiveAdapter,
)


EXPERIMENT_ID = "00000000-0000-0000-0000-000000000201"
HYPOTHESIS_ID = "00000000-0000-0000-0000-000000000202"


def condition(condition_id: str, workload: float) -> MitoQspCondition:
    return MitoQspCondition(
        condition_id=condition_id,
        label=condition_id,
        duration_seconds=0.0001,
        atp_hydrolysis_rate=workload,
        atp_hydrolysis_unit="mol/s/L-cell",
        workload_provenance="SCIENTIFIC_MODEL_ASSUMPTION",
        workload_source_ref="experiment-spec:H-202",
        workload_rationale="Predeclared workload contrast",
        initial_state_overrides=(IndexedValue(
            index=1,
            value=0.01,
            unit="model concentration",
            provenance="MODEL_DEFAULT_OVERRIDE",
            source_ref="experiment-spec:H-202",
            rationale="Predeclared initial state",
        ),),
    )


class MitochondriaQspPassiveAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.model = Path(self.temp.name)
        self.dynamics = self.model / "Cell_dxdT.m"
        self.dynamics.write_bytes(b"pinned-qsp-dynamics")
        self.model_hash = hashlib.sha256(self.dynamics.read_bytes()).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    def request(self, **updates) -> MitoQspExperimentRequest:
        values = dict(
            experiment_id=EXPERIMENT_ID,
            hypothesis_ids=(HYPOTHESIS_ID,),
            model_asset_sha256=self.model_hash,
            baseline=condition("baseline", 0.0005),
            candidates=(condition("candidate", 0.001),),
            requested_state_indices=(1, 7),
            assumptions=("Pinned test runner represents adapter mechanics only",),
            uncertainty_requirements=("No physiological uncertainty quantified",),
        )
        values.update(updates)
        return MitoQspExperimentRequest(**values)

    @staticmethod
    def runner(item: MitoQspCondition, requested: tuple[int, ...]) -> dict:
        multiplier = item.atp_hydrolysis_rate * 1000
        return {
            "state_count": 109,
            "step_count": 3,
            "finite": True,
            "final_time_seconds": item.duration_seconds,
            "requested_state_indices": list(requested),
            "requested_final_values": [index * multiplier for index in requested],
        }

    def test_executes_exact_conditions_and_returns_baseline_deltas(self):
        adapter = MitochondriaQspPassiveAdapter(self.model, runner=self.runner)
        result = adapter.run(self.request())
        self.assertEqual([x.value for x in result.baseline.final_values], [0.5, 3.5])
        self.assertEqual(
            [x.value for x in result.candidates[0].baseline_deltas], [0.5, 3.5]
        )
        self.assertIn("does not judge hypothesis agreement", result.limitations[0])

    def test_model_hash_mismatch_fails_closed(self):
        adapter = MitochondriaQspPassiveAdapter(self.model, runner=self.runner)
        with self.assertRaisesRegex(ValueError, "hash does not match"):
            adapter.run(self.request(model_asset_sha256="0" * 64))

    def test_single_requested_state_accepts_octave_scalar_json(self):
        def scalar_runner(item, requested):
            return {
                "state_count": 109, "step_count": 2, "finite": True,
                "final_time_seconds": item.duration_seconds,
                "requested_state_indices": list(requested),
                "requested_final_values": 2.5,
            }
        adapter = MitochondriaQspPassiveAdapter(self.model, runner=scalar_runner)
        result = adapter.run(self.request(requested_state_indices=(1,)))
        self.assertEqual(result.baseline.final_values[0].value, 2.5)

    def test_duplicate_or_out_of_range_indices_fail_closed(self):
        with self.assertRaises(ValidationError):
            self.request(requested_state_indices=(1, 1))
        with self.assertRaises(ValidationError):
            self.request(requested_state_indices=(110,))

    def test_override_requires_nonempty_provenance_reference(self):
        with self.assertRaises(ValidationError):
            IndexedValue(
                index=1, value=1, unit="M", provenance="ASSUMPTION",
                source_ref="", rationale="Declared",
            )

    def test_batch_preserves_successful_candidates_when_one_condition_fails(self):
        second = condition("candidate-2", 0.0015)
        adapter = MitochondriaQspPassiveAdapter(self.model)
        batch = {
            "complete": True,
            "timed_out": False,
            "results": [
                {"condition_id": "baseline", "ok": True, **self.runner(condition("baseline", 0.0005), (1, 7))},
                {"condition_id": "candidate", "ok": True, **self.runner(condition("candidate", 0.001), (1, 7))},
                {"condition_id": "candidate-2", "ok": False, "error": "solver failed"},
            ],
        }
        with patch.object(adapter, "_execute_batch", return_value=batch):
            result = adapter.run(self.request(candidates=(condition("candidate", 0.001), second)))
        self.assertFalse(result.complete)
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.condition_failures[0].condition_id, "candidate-2")
        self.assertEqual(result.condition_failures[0].error, "solver failed")


if __name__ == "__main__":
    unittest.main()
