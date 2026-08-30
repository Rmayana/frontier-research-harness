from __future__ import annotations

import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from frontier_research_harness.digital_twin_contracts import (
    AggregationRule,
    CalibrationLevel,
    ExchangeVariable,
    FederatedTwinGraph,
    ForecastApplicability,
    ModelPartition,
    TimeResolution,
    TwinSignal,
    TwinSnapshot,
)


HASH = "1" * 64


class DigitalTwinContractTests(unittest.TestCase):
    def test_validates_multirate_exchange(self):
        metabolic = ModelPartition(
            partition_id="metabolic",
            component_id="mitocore",
            resolution=TimeResolution.SECOND,
            calibration=CalibrationLevel.REFERENCE_BOUNDARY,
            model_version="1.01",
            model_hash=HASH,
            declared_outputs=("oxygen_capacity_fraction",),
            maximum_supported_horizon_seconds=60,
        )
        repeated_output = ModelPartition(
            partition_id="repeated-output",
            component_id="evidence-response-model",
            resolution=TimeResolution.SET,
            calibration=CalibrationLevel.POPULATION_PRIOR,
            model_version="evidence-2026-08-29",
            model_hash="2" * 64,
            declared_inputs=("oxygen_capacity_fraction",),
            declared_outputs=("output_decrement",),
            maximum_supported_horizon_seconds=3600,
        )
        graph = FederatedTwinGraph(
            graph_id="combat-athlete-twin-v1",
            partitions=(metabolic, repeated_output),
            exchanges=(ExchangeVariable(
                variable_id="metabolic-to-repeat",
                source_partition_id="metabolic",
                target_partition_id="repeated-output",
                source_output="oxygen_capacity_fraction",
                target_input="oxygen_capacity_fraction",
                unit="1",
                aggregation=AggregationRule.TERMINAL,
                communication_interval_seconds=30,
                uncertainty_standard_deviation=0.1,
                applicability="Generic metabolic boundary only.",
            ),),
        )
        self.assertEqual(len(graph.exchanges), 1)

    def test_rejects_undeclared_exchange(self):
        source = ModelPartition(
            partition_id="a", component_id="a", resolution=TimeResolution.SECOND,
            calibration=CalibrationLevel.REFERENCE_BOUNDARY,
            model_version="1", model_hash=HASH,
            maximum_supported_horizon_seconds=10,
        )
        target = source.model_copy(update={"partition_id": "b", "component_id": "b"})
        with self.assertRaisesRegex(ValidationError, "source output is not declared"):
            FederatedTwinGraph(
                graph_id="bad", partitions=(source, target),
                exchanges=(ExchangeVariable(
                    variable_id="x", source_partition_id="a", target_partition_id="b",
                    source_output="missing", target_input="missing", unit="N",
                    aggregation=AggregationRule.PEAK,
                    communication_interval_seconds=1,
                    uncertainty_standard_deviation=0,
                    applicability="test",
                ),),
            )

    def test_personal_forecast_fails_closed_on_reference_inputs(self):
        with self.assertRaisesRegex(ValidationError, "personally calibrated"):
            ForecastApplicability(
                target_ids=("vo2max",), horizon_seconds=86400,
                input_calibration_levels=(CalibrationLevel.REFERENCE_BOUNDARY,),
                personal_endpoint_claim_allowed=True,
                limitations=("Reference model only.",),
            )

    def test_snapshot_preserves_uncertainty_and_provenance(self):
        observed_at = datetime(2026, 8, 29, tzinfo=timezone.utc)
        signal = TwinSignal(
            signal_id="body_mass", value=79.4, unit="kg", standard_deviation=0.2,
            resolution=TimeResolution.DAY,
            calibration=CalibrationLevel.PERSONAL_OBSERVATION,
            observed_at=observed_at, source_partition_id="scale",
            source_record_hash=HASH,
        )
        snapshot = TwinSnapshot(
            snapshot_id="baseline", observed_at=observed_at,
            signals=(signal,), unresolved_signal_ids=("vo2max",),
        )
        self.assertEqual(snapshot.signals[0].standard_deviation, 0.2)


if __name__ == "__main__":
    unittest.main()
