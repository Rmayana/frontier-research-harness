"""Passive, caller-specified Human-GEM experiments.

The adapter validates and executes an experiment chosen by the Scientific
Model.  It never derives flux bounds from natural language, selects reactions,
or decides whether a hypothesis survived the result.
"""

from __future__ import annotations

import hashlib
import math
from enum import StrEnum
from pathlib import Path
from typing import Callable

from pydantic import Field, model_validator

from frontier_research_harness.scientific_contracts import (
    NonEmptyStr,
    ScientificModel,
    Sha256,
    UuidText,
    canonical_sha256,
)

DEFAULT_HUMAN_GEM_PATH = Path("vendor/Human-GEM/model/Human-GEM.xml")


class OptimizationDirection(StrEnum):
    MAXIMIZE = "MAXIMIZE"
    MINIMIZE = "MINIMIZE"


class ReactionConstraint(ScientificModel):
    reaction_id: NonEmptyStr
    lower_bound: float
    upper_bound: float
    unit: NonEmptyStr
    provenance: NonEmptyStr
    source_ref: NonEmptyStr
    rationale: NonEmptyStr

    @model_validator(mode="after")
    def finite_ordered_bounds(self) -> "ReactionConstraint":
        if not math.isfinite(self.lower_bound) or not math.isfinite(self.upper_bound):
            raise ValueError("reaction bounds must be finite")
        if self.lower_bound > self.upper_bound:
            raise ValueError("reaction lower_bound cannot exceed upper_bound")
        return self


class MetabolicCondition(ScientificModel):
    condition_id: NonEmptyStr
    label: NonEmptyStr
    constraints: tuple[ReactionConstraint, ...]

    @model_validator(mode="after")
    def reaction_constraints_are_unique(self) -> "MetabolicCondition":
        ids = [item.reaction_id for item in self.constraints]
        if len(ids) != len(set(ids)):
            raise ValueError("condition reaction constraints must be unique")
        return self


class ObjectiveTerm(ScientificModel):
    reaction_id: NonEmptyStr
    coefficient: float
    provenance: NonEmptyStr
    source_ref: NonEmptyStr
    rationale: NonEmptyStr

    @model_validator(mode="after")
    def coefficient_is_finite_nonzero(self) -> "ObjectiveTerm":
        if not math.isfinite(self.coefficient) or self.coefficient == 0:
            raise ValueError("objective coefficient must be finite and nonzero")
        return self


class MetabolicObjective(ScientificModel):
    direction: OptimizationDirection
    terms: tuple[ObjectiveTerm, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def reaction_terms_are_unique(self) -> "MetabolicObjective":
        ids = [item.reaction_id for item in self.terms]
        if len(ids) != len(set(ids)):
            raise ValueError("objective reaction terms must be unique")
        return self


class HumanGemExperimentRequest(ScientificModel):
    experiment_id: UuidText
    hypothesis_ids: tuple[UuidText, ...] = Field(min_length=1)
    model_asset_sha256: Sha256
    baseline: MetabolicCondition
    candidates: tuple[MetabolicCondition, ...] = Field(min_length=1)
    objective: MetabolicObjective
    requested_flux_reaction_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    assumptions: tuple[NonEmptyStr, ...] = Field(min_length=1)
    uncertainty_requirements: tuple[NonEmptyStr, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def condition_and_output_ids_are_unique(self) -> "HumanGemExperimentRequest":
        condition_ids = [self.baseline.condition_id, *(x.condition_id for x in self.candidates)]
        if len(condition_ids) != len(set(condition_ids)):
            raise ValueError("baseline and candidate condition IDs must be unique")
        if len(self.requested_flux_reaction_ids) != len(set(self.requested_flux_reaction_ids)):
            raise ValueError("requested flux reaction IDs must be unique")
        return self


class ReactionFlux(ScientificModel):
    reaction_id: NonEmptyStr
    value: float


class MetabolicConditionResult(ScientificModel):
    condition_id: NonEmptyStr
    solver_status: NonEmptyStr
    objective_value: float
    fluxes: tuple[ReactionFlux, ...]
    baseline_flux_deltas: tuple[ReactionFlux, ...]
    applied_constraints: tuple[ReactionConstraint, ...]


class HumanGemExperimentResult(ScientificModel):
    experiment_id: UuidText
    hypothesis_ids: tuple[UuidText, ...]
    simulator_model: NonEmptyStr = "Human-GEM"
    simulator_version: NonEmptyStr
    solver: NonEmptyStr
    input_hash: Sha256
    model_asset_sha256: Sha256
    baseline: MetabolicConditionResult
    candidates: tuple[MetabolicConditionResult, ...]
    uncertainties: tuple[NonEmptyStr, ...]
    limitations: tuple[NonEmptyStr, ...] = Field(min_length=1)


class HumanGemPassiveAdapter:
    """Execute exact caller-provided constraints against one pinned SBML asset."""

    def __init__(
        self,
        model_path: str | Path = DEFAULT_HUMAN_GEM_PATH,
        *,
        model_version: str = "2.0.0",
        model_loader: Callable[[str], object] | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.model_version = model_version
        self._model_loader = model_loader

    @staticmethod
    def _sha256(path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _load_model(self):
        if self._model_loader is not None:
            return self._model_loader(str(self.model_path))
        from cobra.io import read_sbml_model
        return read_sbml_model(str(self.model_path))

    @staticmethod
    def _all_reaction_ids(request: HumanGemExperimentRequest) -> set[str]:
        ids = set(request.requested_flux_reaction_ids)
        ids.update(term.reaction_id for term in request.objective.terms)
        for condition in (request.baseline, *request.candidates):
            ids.update(item.reaction_id for item in condition.constraints)
        return ids

    def _run_condition(self, model, condition: MetabolicCondition, request: HumanGemExperimentRequest):
        with model:
            for constraint in condition.constraints:
                reaction = model.reactions.get_by_id(constraint.reaction_id)
                reaction.bounds = (constraint.lower_bound, constraint.upper_bound)
            model.objective = {
                model.reactions.get_by_id(term.reaction_id): term.coefficient
                for term in request.objective.terms
            }
            model.objective_direction = request.objective.direction.value.lower()
            solution = model.optimize()
            if solution.status != "optimal":
                raise RuntimeError(
                    f"Human-GEM condition {condition.condition_id} was not optimal: {solution.status}"
                )
            fluxes = tuple(
                ReactionFlux(reaction_id=reaction_id, value=float(solution.fluxes[reaction_id]))
                for reaction_id in request.requested_flux_reaction_ids
            )
            return solution, fluxes

    def run(self, request: HumanGemExperimentRequest) -> HumanGemExperimentResult:
        if not self.model_path.is_file():
            raise FileNotFoundError(self.model_path)
        actual_hash = self._sha256(self.model_path)
        if actual_hash.casefold() != request.model_asset_sha256.casefold():
            raise ValueError("Human-GEM model asset hash does not match request")
        model = self._load_model()
        model_reactions = {reaction.id for reaction in model.reactions}
        missing = sorted(self._all_reaction_ids(request) - model_reactions)
        if missing:
            raise ValueError(f"Human-GEM reaction IDs do not exist: {', '.join(missing)}")

        baseline_solution, baseline_fluxes = self._run_condition(model, request.baseline, request)
        baseline_by_id = {item.reaction_id: item.value for item in baseline_fluxes}
        baseline_result = MetabolicConditionResult(
            condition_id=request.baseline.condition_id,
            solver_status=baseline_solution.status,
            objective_value=float(baseline_solution.objective_value),
            fluxes=baseline_fluxes,
            baseline_flux_deltas=tuple(
                ReactionFlux(reaction_id=item.reaction_id, value=0.0)
                for item in baseline_fluxes
            ),
            applied_constraints=request.baseline.constraints,
        )
        candidate_results: list[MetabolicConditionResult] = []
        for condition in request.candidates:
            solution, fluxes = self._run_condition(model, condition, request)
            candidate_results.append(MetabolicConditionResult(
                condition_id=condition.condition_id,
                solver_status=solution.status,
                objective_value=float(solution.objective_value),
                fluxes=fluxes,
                baseline_flux_deltas=tuple(
                    ReactionFlux(
                        reaction_id=item.reaction_id,
                        value=item.value - baseline_by_id[item.reaction_id],
                    )
                    for item in fluxes
                ),
                applied_constraints=condition.constraints,
            ))
        return HumanGemExperimentResult(
            experiment_id=request.experiment_id,
            hypothesis_ids=request.hypothesis_ids,
            simulator_version=self.model_version,
            solver=str(model.solver.interface.__name__),
            input_hash=canonical_sha256(request),
            model_asset_sha256=actual_hash,
            baseline=baseline_result,
            candidates=tuple(candidate_results),
            uncertainties=request.uncertainty_requirements,
            limitations=(
                "MODEL_RESULT only; the adapter does not judge hypothesis agreement.",
                "Flux bounds, objective terms, and biological interpretation remain caller-supplied assumptions.",
                "Generic Human-GEM is not calibrated to the user's tissues, diet, exercise, or time-varying physiology.",
                "Steady-state FBA does not establish real-world intervention efficacy or safety.",
            ),
        )


__all__ = [name for name in globals() if not name.startswith("_")]
