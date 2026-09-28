"""Traceable retained statements without adding a research workflow."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field, model_validator

from frontier_research_harness.scientific_contracts import NonEmptyStr, ScientificModel


class SupportStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    USER_OBSERVATION = "USER_OBSERVATION"
    MODEL_BOUND = "MODEL_BOUND"
    MEASUREMENT_DERIVED = "MEASUREMENT_DERIVED"
    HYPOTHESIS = "HYPOTHESIS"
    INFERENCE = "INFERENCE"
    UNKNOWN = "UNKNOWN"


class ResearchStatement(ScientificModel):
    """One concise statement with explicit epistemic type and receipts."""

    statement: NonEmptyStr
    support_status: SupportStatus
    target_ids: tuple[NonEmptyStr, ...] = ()
    evidence_ids: tuple[NonEmptyStr, ...] = ()
    experiment_ids: tuple[NonEmptyStr, ...] = ()
    calculation_ids: tuple[NonEmptyStr, ...] = ()
    observation_ids: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def required_receipt_matches_status(self) -> "ResearchStatement":
        required = {
            SupportStatus.SUPPORTED: self.evidence_ids,
            SupportStatus.USER_OBSERVATION: self.observation_ids,
            SupportStatus.MODEL_BOUND: self.experiment_ids,
            SupportStatus.MEASUREMENT_DERIVED: self.calculation_ids,
        }.get(self.support_status)
        if required is not None and not required:
            field = {
                SupportStatus.SUPPORTED: "evidence_ids",
                SupportStatus.USER_OBSERVATION: "observation_ids",
                SupportStatus.MODEL_BOUND: "experiment_ids",
                SupportStatus.MEASUREMENT_DERIVED: "calculation_ids",
            }[self.support_status]
            raise ValueError(f"{self.support_status.value} requires non-empty {field}")
        for name in (
            "target_ids",
            "evidence_ids",
            "experiment_ids",
            "calculation_ids",
            "observation_ids",
        ):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must contain unique IDs")
        return self


class ResearchEntry(ScientificModel):
    """Optional joint research note; never an approval or verified observation."""
    author: Literal["USER", "CODEX"]
    text: NonEmptyStr
    label: NonEmptyStr | None = None
    in_reply_to: NonEmptyStr | None = None
    references: list[NonEmptyStr] = Field(default_factory=list)
    session_id: NonEmptyStr | None = None
    agent_id: NonEmptyStr | None = None

    @model_validator(mode="after")
    def agent_is_not_human(self) -> "ResearchEntry":
        if self.agent_id and self.author != "CODEX":
            raise ValueError("agent contributions must use author CODEX, not USER")
        return self


__all__ = ["ResearchStatement", "SupportStatus"]
