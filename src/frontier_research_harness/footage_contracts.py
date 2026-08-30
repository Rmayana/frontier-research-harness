"""Strict primary-footage observations for boxing technique research."""
from __future__ import annotations

from pydantic import Field, model_validator

from frontier_research_harness.scientific_contracts import NonEmptyStr, ScientificModel


class FootageObservation(ScientificModel):
    source: NonEmptyStr
    reference_url: NonEmptyStr
    title: NonEmptyStr
    athlete: NonEmptyStr
    opponent_or_context: NonEmptyStr
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    observed_actions: tuple[NonEmptyStr, ...] = Field(min_length=1)
    situational_conditions: tuple[NonEmptyStr, ...] = Field(min_length=1)
    repeated_pattern: bool | None = None
    derived_drills: tuple[NonEmptyStr, ...] = ()
    applicability: NonEmptyStr
    limitations: tuple[NonEmptyStr, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def timestamps_are_ordered(self) -> "FootageObservation":
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds")
        return self

    def evidence_record(self) -> dict[str, object]:
        source_record = self.model_dump(mode="json")
        claims = [
            f"At {self.start_seconds:.3f}-{self.end_seconds:.3f}s: {action}"
            for action in self.observed_actions
        ]
        return {
            "source": self.source,
            "reference_url": self.reference_url,
            "classification": "EXTERNAL_PRIMARY_SOURCE",
            "title": self.title,
            "content_level": "primary_source_observation",
            "retained_claims": claims,
            "applicability": self.applicability,
            "limitations": list(self.limitations),
            "source_record": source_record,
        }


__all__ = ["FootageObservation"]
