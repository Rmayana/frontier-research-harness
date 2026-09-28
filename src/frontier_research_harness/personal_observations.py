"""Unit- and protocol-aware personal observations for descriptive calibration."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field, model_validator

from frontier_research_harness.scientific_contracts import (
    NonEmptyStr,
    ScientificModel,
    canonical_sha256,
)


class ObservationSource(str, Enum):
    USER_REPORTED = "USER_REPORTED"
    DEVICE = "DEVICE"
    LAB = "LAB"
    COACH_OR_RATER = "COACH_OR_RATER"
    IMPORTED_RECORD = "IMPORTED_RECORD"


class PersonalObservation(ScientificModel):
    """One immutable numerical observation, not an efficacy or causal claim."""

    observed_at: datetime
    target_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    metric: NonEmptyStr
    value: float
    unit: NonEmptyStr
    protocol: NonEmptyStr
    source_type: ObservationSource
    instrument: NonEmptyStr | None = None
    session_id: NonEmptyStr | None = None
    uncertainty: float | None = Field(default=None, ge=0)
    uncertainty_unit: NonEmptyStr | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    provenance: tuple[dict[str, Any], ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_observation(self) -> "PersonalObservation":
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must include a timezone offset")
        if len(self.target_ids) != len(set(self.target_ids)):
            raise ValueError("target_ids must contain unique IDs")
        if any(not item for item in self.provenance):
            raise ValueError("provenance entries must be non-empty objects")
        if self.uncertainty is not None and self.uncertainty_unit is None:
            raise ValueError("uncertainty_unit is required when uncertainty is supplied")
        return self

    def protocol_hash(self) -> str:
        return canonical_sha256(
            {
                "target_ids": sorted(self.target_ids),
                "metric": self.metric,
                "unit": self.unit,
                "protocol": self.protocol,
                "instrument": self.instrument,
            }
        )

    def record_hash(self) -> str:
        return canonical_sha256(self.model_dump(mode="json"))


__all__ = ["ObservationSource", "PersonalObservation"]
