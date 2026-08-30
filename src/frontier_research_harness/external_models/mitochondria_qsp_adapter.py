"""Passive execution of caller-specified mitochondrial QSP model experiments."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from pydantic import Field, model_validator

from frontier_research_harness.scientific_contracts import (
    NonEmptyStr, ScientificModel, Sha256, UuidText, canonical_sha256,
)


DEFAULT_MODEL_PATH = Path("vendor/mitochondria-metabolism")
DEFAULT_OCTAVE_PATH = Path(
    "C:/Program Files/GNU Octave/Octave-11.3.0/mingw64/bin/octave-cli.exe"
)
DEFAULT_DRIVER_PATH = Path("scripts/external_engines/mitochondria_qsp_experiment.m")


class IndexedValue(ScientificModel):
    index: int = Field(ge=1)
    value: float
    unit: NonEmptyStr
    provenance: NonEmptyStr
    source_ref: NonEmptyStr
    rationale: NonEmptyStr

    @model_validator(mode="after")
    def value_is_finite(self) -> "IndexedValue":
        if not math.isfinite(self.value):
            raise ValueError("indexed value must be finite")
        return self


class MitoQspCondition(ScientificModel):
    condition_id: NonEmptyStr
    label: NonEmptyStr
    duration_seconds: float = Field(gt=0, le=2000)
    atp_hydrolysis_rate: float = Field(ge=0)
    atp_hydrolysis_unit: NonEmptyStr
    workload_provenance: NonEmptyStr
    workload_source_ref: NonEmptyStr
    workload_rationale: NonEmptyStr
    initial_state_overrides: tuple[IndexedValue, ...] = ()
    parameter_overrides: tuple[IndexedValue, ...] = ()

    @model_validator(mode="after")
    def indices_are_valid_and_unique(self) -> "MitoQspCondition":
        if not math.isfinite(self.duration_seconds) or not math.isfinite(self.atp_hydrolysis_rate):
            raise ValueError("duration and ATP hydrolysis rate must be finite")
        for values, maximum, label in (
            (self.initial_state_overrides, 109, "initial state"),
            (self.parameter_overrides, 45, "parameter"),
        ):
            indices = [item.index for item in values]
            if len(indices) != len(set(indices)):
                raise ValueError(f"{label} override indices must be unique")
            if any(index > maximum for index in indices):
                raise ValueError(f"{label} override index exceeds pinned model range")
        return self


class MitoQspExperimentRequest(ScientificModel):
    experiment_id: UuidText
    hypothesis_ids: tuple[UuidText, ...] = Field(min_length=1)
    model_asset_sha256: Sha256
    baseline: MitoQspCondition
    candidates: tuple[MitoQspCondition, ...] = Field(min_length=1)
    requested_state_indices: tuple[int, ...] = Field(min_length=1)
    assumptions: tuple[NonEmptyStr, ...] = Field(min_length=1)
    uncertainty_requirements: tuple[NonEmptyStr, ...] = Field(min_length=1)
    timeout_seconds: int = Field(default=300, ge=1, le=86_400)

    @model_validator(mode="after")
    def condition_and_state_ids_are_valid(self) -> "MitoQspExperimentRequest":
        ids = [self.baseline.condition_id, *(item.condition_id for item in self.candidates)]
        if len(ids) != len(set(ids)):
            raise ValueError("baseline and candidate condition IDs must be unique")
        if len(self.requested_state_indices) != len(set(self.requested_state_indices)):
            raise ValueError("requested state indices must be unique")
        if any(index < 1 or index > 109 for index in self.requested_state_indices):
            raise ValueError("requested state index exceeds pinned model range")
        return self


class StateValue(ScientificModel):
    state_index: int
    value: float


class MitoQspConditionResult(ScientificModel):
    condition_id: NonEmptyStr
    final_time_seconds: float
    step_count: int = Field(ge=1)
    final_values: tuple[StateValue, ...]
    baseline_deltas: tuple[StateValue, ...]
    applied_condition: MitoQspCondition


class MitoQspConditionFailure(ScientificModel):
    condition_id: NonEmptyStr
    error: NonEmptyStr


class MitoQspExperimentResult(ScientificModel):
    experiment_id: UuidText
    hypothesis_ids: tuple[UuidText, ...]
    simulator_model: NonEmptyStr = "Myocardial Mitochondria Metabolism QSP"
    simulator_version: NonEmptyStr = "git:e7513d3dca20673bfee0bfebaff41132009593e5"
    solver: NonEmptyStr = "GNU Octave ode15s"
    input_hash: Sha256
    model_asset_sha256: Sha256
    baseline: MitoQspConditionResult
    candidates: tuple[MitoQspConditionResult, ...]
    condition_failures: tuple[MitoQspConditionFailure, ...] = ()
    complete: bool = True
    timed_out: bool = False
    uncertainties: tuple[NonEmptyStr, ...]
    limitations: tuple[NonEmptyStr, ...] = Field(min_length=1)


Runner = Callable[[MitoQspCondition, tuple[int, ...]], dict]


class MitochondriaQspPassiveAdapter:
    def __init__(
        self,
        model_path: str | Path = DEFAULT_MODEL_PATH,
        octave_path: str | Path = DEFAULT_OCTAVE_PATH,
        driver_path: str | Path = DEFAULT_DRIVER_PATH,
        *,
        runner: Runner | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.octave_path = Path(octave_path)
        self.driver_path = Path(driver_path)
        self._runner = runner

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256(path.read_bytes())
        return digest.hexdigest()

    def _execute(self, condition: MitoQspCondition, requested: tuple[int, ...]) -> dict:
        if self._runner is not None:
            return self._runner(condition, requested)
        raise RuntimeError("single-condition execution is reserved for injected test runners")

    @staticmethod
    def _condition_payload(condition: MitoQspCondition) -> dict:
        return {
            "condition_id": condition.condition_id,
            "duration_seconds": condition.duration_seconds,
            "atp_hydrolysis_rate": condition.atp_hydrolysis_rate,
            "initial_state_indices": [item.index for item in condition.initial_state_overrides],
            "initial_state_values": [item.value for item in condition.initial_state_overrides],
            "parameter_indices": [item.index for item in condition.parameter_overrides],
            "parameter_values": [item.value for item in condition.parameter_overrides],
        }

    def _execute_batch(
        self,
        conditions: tuple[MitoQspCondition, ...],
        requested: tuple[int, ...],
        timeout_seconds: int,
    ) -> dict:
        for path in (self.model_path, self.octave_path, self.driver_path):
            if not path.exists():
                raise FileNotFoundError(path)
        payload = {
            "conditions": [self._condition_payload(condition) for condition in conditions],
            "requested_state_indices": list(requested),
        }
        with tempfile.TemporaryDirectory(prefix="mitochondria-qsp-") as temporary:
            input_path = Path(temporary) / "input.json"
            output_path = Path(temporary) / "output.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            try:
                completed = subprocess.run(
                    (str(self.octave_path.resolve()), "--quiet", "--no-gui",
                     str(self.driver_path.resolve()), str(self.model_path.resolve()),
                     str(input_path), str(output_path)),
                    text=True, capture_output=True, timeout=timeout_seconds, check=False,
                )
            except subprocess.TimeoutExpired as exc:
                if not output_path.is_file():
                    raise RuntimeError(
                        "mitochondrial QSP batch timed out before any condition completed"
                    ) from exc
                partial = json.loads(output_path.read_text(encoding="utf-8"))
                partial["timed_out"] = True
                partial["complete"] = False
                return partial
            if not output_path.is_file():
                raise RuntimeError(
                    f"mitochondrial QSP batch produced no checkpoint: {completed.stderr}"
                )
            result = json.loads(output_path.read_text(encoding="utf-8"))
            if completed.returncode != 0:
                result["process_error"] = completed.stderr[-4000:]
                result["complete"] = False
            return result

    @staticmethod
    def _condition_result(
        condition: MitoQspCondition, raw: dict, requested: tuple[int, ...], baseline: dict[int, float] | None,
    ) -> MitoQspConditionResult:
        if raw.get("state_count") != 109 or not raw.get("finite"):
            raise RuntimeError("mitochondrial QSP returned invalid or non-finite state output")
        raw_values = raw["requested_final_values"]
        if isinstance(raw_values, (int, float)):
            raw_values = [raw_values]
        values = tuple(StateValue(state_index=index, value=float(value)) for index, value in zip(
            requested, raw_values, strict=True
        ))
        return MitoQspConditionResult(
            condition_id=condition.condition_id,
            final_time_seconds=float(raw["final_time_seconds"]),
            step_count=int(raw["step_count"]),
            final_values=values,
            baseline_deltas=tuple(StateValue(
                state_index=item.state_index,
                value=0.0 if baseline is None else item.value - baseline[item.state_index],
            ) for item in values),
            applied_condition=condition,
        )

    def run(self, request: MitoQspExperimentRequest) -> MitoQspExperimentResult:
        dynamics = self.model_path / "Cell_dxdT.m"
        if not dynamics.is_file():
            raise FileNotFoundError(dynamics)
        actual_hash = self._sha256(dynamics)
        if actual_hash.casefold() != request.model_asset_sha256.casefold():
            raise ValueError("mitochondrial QSP model asset hash does not match request")
        conditions = (request.baseline, *request.candidates)
        if self._runner is not None:
            raw_by_id = {
                condition.condition_id: {
                    "condition_id": condition.condition_id,
                    "ok": True,
                    **self._execute(condition, request.requested_state_indices),
                }
                for condition in conditions
            }
            batch_complete = True
            timed_out = False
        else:
            batch = self._execute_batch(
                conditions, request.requested_state_indices, request.timeout_seconds
            )
            raw_results = batch.get("results", [])
            if isinstance(raw_results, dict):
                raw_results = [raw_results]
            raw_by_id = {
                str(item.get("condition_id")): item
                for item in raw_results
                if isinstance(item, dict) and item.get("condition_id")
            }
            batch_complete = bool(batch.get("complete", False))
            timed_out = bool(batch.get("timed_out", False))
        baseline_raw = raw_by_id.get(request.baseline.condition_id)
        if not baseline_raw or not baseline_raw.get("ok", False):
            reason = baseline_raw.get("error") if baseline_raw else "no baseline checkpoint"
            raise RuntimeError(f"mitochondrial QSP baseline failed: {reason}")
        baseline = self._condition_result(
            request.baseline, baseline_raw, request.requested_state_indices, None
        )
        baseline_values = {item.state_index: item.value for item in baseline.final_values}
        candidates: list[MitoQspConditionResult] = []
        failures: list[MitoQspConditionFailure] = []
        for condition in request.candidates:
            raw = raw_by_id.get(condition.condition_id)
            if not raw or not raw.get("ok", False):
                failures.append(MitoQspConditionFailure(
                    condition_id=condition.condition_id,
                    error=str(raw.get("error") if raw else "no condition checkpoint"),
                ))
                continue
            candidates.append(self._condition_result(
                condition, raw, request.requested_state_indices, baseline_values
            ))
        return MitoQspExperimentResult(
            experiment_id=request.experiment_id,
            hypothesis_ids=request.hypothesis_ids,
            input_hash=canonical_sha256(request),
            model_asset_sha256=actual_hash,
            baseline=baseline,
            candidates=tuple(candidates),
            condition_failures=tuple(failures),
            complete=batch_complete and not failures,
            timed_out=timed_out,
            uncertainties=request.uncertainty_requirements,
            limitations=(
                "MODEL_RESULT only; the adapter does not judge hypothesis agreement.",
                "State indices, parameter overrides, workload, and interpretation remain caller-supplied.",
                "The myocardial model is not calibrated to the user's tissues or longitudinal responses.",
                "Numerical execution does not establish intervention efficacy or safety.",
                "A partial result preserves completed conditions but does not substitute for the missing comparisons.",
            ),
        )


__all__ = [name for name in globals() if not name.startswith("_")]
