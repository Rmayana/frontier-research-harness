"""Strict interchange contracts for a federated combat-athlete digital twin.

The contracts deliberately do not implement a whole-body simulator or choose a
training strategy.  They make independently validated model results safe to
exchange across resolutions while keeping personal calibration and uncertainty
explicit.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from frontier_research_harness.scientific_contracts import (
    NonEmptyStr,
    ScientificModel,
    Sha256,
)


UnitText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TimeResolution(StrEnum):
    MILLISECOND = "MILLISECOND"
    SECOND = "SECOND"
    SET = "SET"
    SESSION = "SESSION"
    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"


class CalibrationLevel(StrEnum):
    REFERENCE_BOUNDARY = "REFERENCE_BOUNDARY"
    POPULATION_PRIOR = "POPULATION_PRIOR"
    PERSONAL_OBSERVATION = "PERSONAL_OBSERVATION"
    PERSONAL_CALIBRATED = "PERSONAL_CALIBRATED"


class AggregationRule(StrEnum):
    INSTANTANEOUS = "INSTANTANEOUS"
    PEAK = "PEAK"
    MEAN = "MEAN"
    INTEGRAL = "INTEGRAL"
    TERMINAL = "TERMINAL"


class ModelPartition(ScientificModel):
    """One independently executable model or evidence-derived response model."""

    partition_id: NonEmptyStr
    component_id: NonEmptyStr
    resolution: TimeResolution
    calibration: CalibrationLevel
    model_version: NonEmptyStr
    model_hash: Sha256
    declared_inputs: tuple[NonEmptyStr, ...] = ()
    declared_outputs: tuple[NonEmptyStr, ...] = ()
    maximum_supported_horizon_seconds: float = Field(gt=0)


class ExchangeVariable(ScientificModel):
    """A unit-bearing value passed between two model partitions."""

    variable_id: NonEmptyStr
    source_partition_id: NonEmptyStr
    target_partition_id: NonEmptyStr
    source_output: NonEmptyStr
    target_input: NonEmptyStr
    unit: UnitText
    aggregation: AggregationRule
    communication_interval_seconds: float = Field(gt=0)
    uncertainty_standard_deviation: float = Field(ge=0)
    applicability: NonEmptyStr


class FederatedTwinGraph(ScientificModel):
    """Validated topology only; scheduling and scientific choices stay in Codex."""

    graph_id: NonEmptyStr
    partitions: tuple[ModelPartition, ...] = Field(min_length=1)
    exchanges: tuple[ExchangeVariable, ...] = ()

    @model_validator(mode="after")
    def validate_topology(self) -> "FederatedTwinGraph":
        by_id = {item.partition_id: item for item in self.partitions}
        if len(by_id) != len(self.partitions):
            raise ValueError("partition IDs must be unique")
        exchange_ids: set[str] = set()
        for exchange in self.exchanges:
            if exchange.variable_id in exchange_ids:
                raise ValueError("exchange variable IDs must be unique")
            exchange_ids.add(exchange.variable_id)
            if exchange.source_partition_id == exchange.target_partition_id:
                raise ValueError("an exchange must connect distinct partitions")
            if exchange.source_partition_id not in by_id:
                raise ValueError("exchange source partition is missing")
            if exchange.target_partition_id not in by_id:
                raise ValueError("exchange target partition is missing")
            source = by_id[exchange.source_partition_id]
            target = by_id[exchange.target_partition_id]
            if exchange.source_output not in source.declared_outputs:
                raise ValueError("exchange source output is not declared")
            if exchange.target_input not in target.declared_inputs:
                raise ValueError("exchange target input is not declared")
            if exchange.communication_interval_seconds > source.maximum_supported_horizon_seconds:
                raise ValueError("exchange interval exceeds source model horizon")
        return self


class TwinSignal(ScientificModel):
    signal_id: NonEmptyStr
    value: float
    unit: UnitText
    standard_deviation: float = Field(ge=0)
    resolution: TimeResolution
    calibration: CalibrationLevel
    observed_at: datetime
    source_partition_id: NonEmptyStr
    source_record_hash: Sha256

    @model_validator(mode="after")
    def require_utc(self) -> "TwinSignal":
        if self.observed_at.utcoffset() != timedelta(0):
            raise ValueError("observed_at must be UTC")
        return self


class TwinSnapshot(ScientificModel):
    """A time-indexed state estimate, never an intervention decision."""

    snapshot_id: NonEmptyStr
    observed_at: datetime
    signals: tuple[TwinSignal, ...] = Field(min_length=1)
    unresolved_signal_ids: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def validate_snapshot(self) -> "TwinSnapshot":
        if self.observed_at.utcoffset() != timedelta(0):
            raise ValueError("observed_at must be UTC")
        ids = [item.signal_id for item in self.signals]
        if len(ids) != len(set(ids)):
            raise ValueError("snapshot signal IDs must be unique")
        if set(ids).intersection(self.unresolved_signal_ids):
            raise ValueError("a signal cannot be both estimated and unresolved")
        return self


class ForecastApplicability(ScientificModel):
    """Fail-closed declaration of what a forecast may claim."""

    target_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    horizon_seconds: float = Field(gt=0)
    input_calibration_levels: tuple[CalibrationLevel, ...] = Field(min_length=1)
    personal_endpoint_claim_allowed: bool
    limitations: tuple[NonEmptyStr, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_unqualified_personal_claim(self) -> "ForecastApplicability":
        if self.personal_endpoint_claim_allowed and any(
            item is not CalibrationLevel.PERSONAL_CALIBRATED
            for item in self.input_calibration_levels
        ):
            raise ValueError(
                "personal endpoint claims require every input to be personally calibrated"
            )
        return self


__all__ = [
    "AggregationRule",
    "CalibrationLevel",
    "ExchangeVariable",
    "FederatedTwinGraph",
    "ForecastApplicability",
    "ModelPartition",
    "TimeResolution",
    "TwinSignal",
    "TwinSnapshot",
]
