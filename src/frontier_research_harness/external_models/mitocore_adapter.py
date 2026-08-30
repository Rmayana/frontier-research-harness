"""Passive experiments against the pinned MitoCore asset."""
from __future__ import annotations

from pathlib import Path

from pydantic import Field

from frontier_research_harness.scientific_contracts import (
    NonEmptyStr,
    ScientificModel,
    Sha256,
    UuidText,
)
from .human_gem_adapter import (
    HumanGemExperimentRequest,
    HumanGemPassiveAdapter,
    MetabolicConditionResult,
)


DEFAULT_MITOCORE_PATH = Path("vendor/MitoCore/mitocore_v1.01.xml")


class MitoCoreExperimentRequest(HumanGemExperimentRequest):
    """Same explicit FBA contract, bound to MitoCore by the adapter."""


class MitoCoreExperimentResult(ScientificModel):
    experiment_id: UuidText
    hypothesis_ids: tuple[UuidText, ...]
    simulator_model: NonEmptyStr = "MitoCore"
    simulator_version: NonEmptyStr
    solver: NonEmptyStr
    input_hash: Sha256
    model_asset_sha256: Sha256
    baseline: MetabolicConditionResult
    candidates: tuple[MetabolicConditionResult, ...]
    uncertainties: tuple[NonEmptyStr, ...]
    limitations: tuple[NonEmptyStr, ...] = Field(min_length=1)


class MitoCorePassiveAdapter(HumanGemPassiveAdapter):
    def __init__(
        self,
        model_path: str | Path = DEFAULT_MITOCORE_PATH,
        *,
        model_version: str = "1.01",
        model_loader=None,
    ) -> None:
        super().__init__(
            model_path, model_version=model_version, model_loader=model_loader
        )

    def run(self, request: MitoCoreExperimentRequest) -> MitoCoreExperimentResult:
        raw = super().run(request)
        return MitoCoreExperimentResult(
            experiment_id=raw.experiment_id,
            hypothesis_ids=raw.hypothesis_ids,
            simulator_version=self.model_version,
            solver=raw.solver,
            input_hash=raw.input_hash,
            model_asset_sha256=raw.model_asset_sha256,
            baseline=raw.baseline,
            candidates=raw.candidates,
            uncertainties=raw.uncertainties,
            limitations=(
                "MODEL_RESULT only; the adapter does not judge hypothesis agreement.",
                "Reaction bounds, objective terms, and biological interpretation remain caller-supplied assumptions.",
                "MitoCore is a compact curated mitochondrial reference, not a whole-person or tissue-calibrated model.",
                "Steady-state FBA and technical executability do not establish intervention efficacy, safety, or personal prediction.",
            ),
        )


__all__ = [name for name in globals() if not name.startswith("_")]
