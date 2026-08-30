"""Deterministic calculations for the fixed physical performance targets.

The calculator owns arithmetic, units, and reproducibility only.  It does not
predict longitudinal adaptation or decide whether a target is attainable.
"""
from __future__ import annotations

import math
from enum import StrEnum
from typing import Any, Callable

from pydantic import Field, model_validator

from frontier_research_harness.scientific_contracts import (
    NonEmptyStr,
    ScientificModel,
    Sha256,
    canonical_sha256,
)


class CalculationEvidenceClass(StrEnum):
    EXACT = "EXACT"
    DATA_DERIVED = "DATA_DERIVED"


class CalculationStatus(StrEnum):
    CALCULATED = "CALCULATED"
    INPUT_REQUIRED = "INPUT_REQUIRED"


class TargetCalculationRequest(ScientificModel):
    target_id: NonEmptyStr
    inputs: dict[str, float | list[float]] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    method: str | None = None

    @model_validator(mode="after")
    def inputs_are_finite(self) -> "TargetCalculationRequest":
        for name, value in self.inputs.items():
            values = value if isinstance(value, list) else [value]
            if not values:
                raise ValueError(f"{name} cannot be an empty series")
            if any(isinstance(item, bool) or not math.isfinite(float(item)) for item in values):
                raise ValueError(f"{name} must contain only finite numbers")
        unknown_units = sorted(set(self.units) - set(self.inputs))
        if unknown_units:
            raise ValueError("units reference absent inputs: " + ", ".join(unknown_units))
        return self


class TargetCalculationResult(ScientificModel):
    status: CalculationStatus
    target_id: NonEmptyStr
    target: NonEmptyStr
    formula_id: NonEmptyStr
    formula_version: NonEmptyStr = "1.0.0"
    evidence_class: CalculationEvidenceClass
    required_inputs: tuple[NonEmptyStr, ...]
    missing_inputs: tuple[NonEmptyStr, ...] = ()
    value: float | None = None
    unit: str | None = None
    meets_target_floor: bool | None = None
    formula: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    input_hash: Sha256
    limitations: tuple[NonEmptyStr, ...] = (
        "This is deterministic arithmetic or a measurement-derived metric, not a biological forecast.",
    )


class _TargetSpec:
    def __init__(
        self,
        target: str,
        required: tuple[str, ...],
        formula: str,
        unit: str,
        compute: Callable[[TargetCalculationRequest], tuple[float, dict[str, Any]]],
        meets: Callable[[float], bool],
        *,
        evidence_class: CalculationEvidenceClass = CalculationEvidenceClass.DATA_DERIVED,
    ) -> None:
        self.target = target
        self.required = required
        self.formula = formula
        self.unit = unit
        self.compute = compute
        self.meets = meets
        self.evidence_class = evidence_class


def _scalar(request: TargetCalculationRequest, name: str, unit: str) -> float:
    value = request.inputs[name]
    if isinstance(value, list):
        raise ValueError(f"{name} must be a scalar")
    supplied = request.units.get(name)
    if supplied != unit:
        raise ValueError(f"{name} unit must be {unit!r}, received {supplied!r}")
    return float(value)


def _same_unit_pair(request: TargetCalculationRequest, first: str, second: str) -> tuple[float, float, str]:
    left = request.inputs[first]
    right = request.inputs[second]
    if isinstance(left, list) or isinstance(right, list):
        raise ValueError(f"{first} and {second} must be scalars")
    left_unit = request.units.get(first)
    right_unit = request.units.get(second)
    if not left_unit or left_unit != right_unit:
        raise ValueError(f"{first} and {second} must use the same declared unit")
    return float(left), float(right), left_unit


def _positive(value: float, name: str) -> float:
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _normalized(numerator_name: str, numerator_unit: str) -> Callable[[TargetCalculationRequest], tuple[float, dict[str, Any]]]:
    def calculate(request: TargetCalculationRequest) -> tuple[float, dict[str, Any]]:
        numerator = _scalar(request, numerator_name, numerator_unit)
        mass = _positive(_scalar(request, "body_mass_kg", "kg"), "body_mass_kg")
        return numerator / mass, {"numerator": numerator, "body_mass_kg": mass}
    return calculate


def _direct(name: str, unit: str) -> Callable[[TargetCalculationRequest], tuple[float, dict[str, Any]]]:
    def calculate(request: TargetCalculationRequest) -> tuple[float, dict[str, Any]]:
        value = _scalar(request, name, unit)
        return value, {"observed_value": value}
    return calculate


def _rfd(window_seconds: float) -> Callable[[TargetCalculationRequest], tuple[float, dict[str, Any]]]:
    def calculate(request: TargetCalculationRequest) -> tuple[float, dict[str, Any]]:
        onset = _scalar(request, "force_onset_n", "N")
        endpoint = _scalar(request, "force_endpoint_n", "N")
        return (endpoint - onset) / window_seconds / 1000.0, {
            "window_seconds": window_seconds,
            "force_change_n": endpoint - onset,
        }
    return calculate


def _retention(request: TargetCalculationRequest) -> tuple[float, dict[str, Any]]:
    initial, final, unit = _same_unit_pair(request, "initial_value", "final_value")
    _positive(initial, "initial_value")
    return final / initial * 100.0, {"measurement_unit": unit}


def _decrement(request: TargetCalculationRequest) -> tuple[float, dict[str, Any]]:
    before, after, unit = _same_unit_pair(request, "before_value", "after_value")
    _positive(before, "before_value")
    return (before - after) / before * 100.0, {"measurement_unit": unit}


def _asymmetry(request: TargetCalculationRequest) -> tuple[float, dict[str, Any]]:
    left, right, unit = _same_unit_pair(request, "left_value", "right_value")
    denominator = max(abs(left), abs(right))
    _positive(denominator, "maximum absolute side value")
    return abs(left - right) / denominator * 100.0, {
        "measurement_unit": unit,
        "method": "absolute difference divided by the larger absolute side",
    }


def _cmj_height(request: TargetCalculationRequest) -> tuple[float, dict[str, Any]]:
    method = request.method or "flight_time"
    if method != "flight_time":
        raise ValueError("cmj_height currently supports method='flight_time' only")
    flight_time = _positive(_scalar(request, "flight_time_s", "s"), "flight_time_s")
    gravity = 9.80665
    return gravity * flight_time**2 / 8.0 * 100.0, {
        "method": method,
        "standard_gravity_m_s2": gravity,
    }


def _absolute_kw(request: TargetCalculationRequest) -> tuple[float, dict[str, Any]]:
    watts = _scalar(request, "peak_power_w", "W")
    return watts / 1000.0, {"peak_power_w": watts}


def _repeated_decrement(request: TargetCalculationRequest) -> tuple[float, dict[str, Any]]:
    outputs = request.inputs["outputs_w"]
    if not isinstance(outputs, list) or len(outputs) < 2:
        raise ValueError("outputs_w must contain at least two repetitions")
    if request.units.get("outputs_w") != "W":
        raise ValueError("outputs_w unit must be 'W'")
    values = [float(item) for item in outputs]
    best = _positive(max(values), "best repeated output")
    return (best - values[-1]) / best * 100.0, {
        "method": "best_to_final",
        "repetition_count": len(values),
        "best_w": best,
        "final_w": values[-1],
    }


def _grip(request: TargetCalculationRequest) -> tuple[float, dict[str, Any]]:
    kgf = _scalar(request, "grip_kgf", "kgf")
    return kgf, {"force_n": kgf * 9.80665, "standard_gravity_m_s2": 9.80665}


def _lateral_neck(request: TargetCalculationRequest) -> tuple[float, dict[str, Any]]:
    left = _scalar(request, "left_force_n", "N")
    right = _scalar(request, "right_force_n", "N")
    return min(left, right), {"left_force_n": left, "right_force_n": right, "aggregation": "weaker_side"}


def _vo2max(request: TargetCalculationRequest) -> tuple[float, dict[str, Any]]:
    absolute = _scalar(request, "oxygen_consumption_ml_min", "ml/min")
    mass = _positive(_scalar(request, "body_mass_kg", "kg"), "body_mass_kg")
    return absolute / mass, {"oxygen_consumption_ml_min": absolute, "body_mass_kg": mass}


def _hrr(request: TargetCalculationRequest) -> tuple[float, dict[str, Any]]:
    end = _scalar(request, "exercise_end_bpm", "bpm")
    one_minute = _scalar(request, "heart_rate_1min_bpm", "bpm")
    return end - one_minute, {"exercise_end_bpm": end, "heart_rate_1min_bpm": one_minute}


def _adherence(request: TargetCalculationRequest) -> tuple[float, dict[str, Any]]:
    completed = _scalar(request, "completed_sessions", "count")
    planned = _positive(_scalar(request, "planned_sessions", "count"), "planned_sessions")
    if completed < 0 or completed > planned:
        raise ValueError("completed_sessions must be between zero and planned_sessions")
    return completed / planned * 100.0, {"completed_sessions": completed, "planned_sessions": planned}


def _under(limit: float) -> Callable[[float], bool]:
    return lambda value: value <= limit


def _over(floor: float) -> Callable[[float], bool]:
    return lambda value: value >= floor


TARGET_SPECS: dict[str, _TargetSpec] = {
    "imtp_peak_force": _TargetSpec("60–70 N/kg", ("peak_force_n", "body_mass_kg"), "peak_force_n / body_mass_kg", "N/kg", _normalized("peak_force_n", "N"), _over(60)),
    "rfd_0_50_ms": _TargetSpec("≥25 kN/s", ("force_onset_n", "force_endpoint_n"), "(force_endpoint_n - force_onset_n) / 0.050 / 1000", "kN/s", _rfd(0.050), _over(25)),
    "rfd_0_250_ms": _TargetSpec("≥12–15 kN/s", ("force_onset_n", "force_endpoint_n"), "(force_endpoint_n - force_onset_n) / 0.250 / 1000", "kN/s", _rfd(0.250), _over(12)),
    "cmj_height": _TargetSpec("100 cm+", ("flight_time_s",), "g * flight_time_s^2 / 8", "cm", _cmj_height, _over(100)),
    "cmj_relative_peak_power": _TargetSpec("≥65 W/kg", ("peak_power_w", "body_mass_kg"), "peak_power_w / body_mass_kg", "W/kg", _normalized("peak_power_w", "W"), _over(65)),
    "cmj_absolute_peak_power": _TargetSpec("≥7.5–8.5 kW", ("peak_power_w",), "peak_power_w / 1000", "kW", _absolute_kw, _over(7.5)),
    "wingate_peak_power": _TargetSpec("18–20 W/kg", ("peak_power_w", "body_mass_kg"), "peak_power_w / body_mass_kg", "W/kg", _normalized("peak_power_w", "W"), _over(18)),
    "wingate_mean_power": _TargetSpec("11–12 W/kg", ("mean_power_w", "body_mass_kg"), "mean_power_w / body_mass_kg", "W/kg", _normalized("mean_power_w", "W"), _over(11)),
    "repeated_explosive_output_decrement": _TargetSpec("≤5%", ("outputs_w",), "(best_output - final_output) / best_output * 100", "%", _repeated_decrement, _under(5)),
    "one_hand_crush_grip": _TargetSpec("110–120+ kgf", ("grip_kgf",), "grip_kgf", "kgf", _grip, _over(110)),
    "grip_endurance_60s": _TargetSpec("초기 최대힘의 ≥70% 유지", ("initial_value", "final_value"), "final_value / initial_value * 100", "%", _retention, _over(70)),
    "neck_flexion_force": _TargetSpec("700–800 N", ("force_n",), "force_n", "N", _direct("force_n", "N"), _over(700)),
    "neck_extension_force": _TargetSpec("950–1100 N", ("force_n",), "force_n", "N", _direct("force_n", "N"), _over(950)),
    "neck_lateral_flexion_force": _TargetSpec("좌·우 800–950 N급", ("left_force_n", "right_force_n"), "min(left_force_n, right_force_n)", "N", _lateral_neck, _over(800)),
    "trunk_rotation_antirotation_torque": _TargetSpec("동체급 최상위 1% 이상", ("reference_percentile",), "reference_percentile", "percentile", _direct("reference_percentile", "percentile"), _over(99)),
    "isometric_force_retention_30s": _TargetSpec("30초 후 ≥70%", ("initial_value", "final_value"), "final_value / initial_value * 100", "%", _retention, _over(70)),
    "simple_visual_reaction_time": _TargetSpec("≤130–140 ms", ("reaction_time_ms",), "reaction_time_ms", "ms", _direct("reaction_time_ms", "ms"), _under(140)),
    "choice_reaction_time": _TargetSpec("≤180–200 ms", ("reaction_time_ms",), "reaction_time_ms", "ms", _direct("reaction_time_ms", "ms"), _under(200)),
    "dynamic_balance_asymmetry": _TargetSpec("≤3%", ("left_value", "right_value"), "abs(left-right) / max(abs(left), abs(right)) * 100", "%", _asymmetry, _under(3)),
    "whole_body_force_power_asymmetry": _TargetSpec("≤3%", ("left_value", "right_value"), "abs(left-right) / max(abs(left), abs(right)) * 100", "%", _asymmetry, _under(3)),
    "fatigued_dynamic_joint_stability_decrement": _TargetSpec("≤5%", ("before_value", "after_value"), "(before-after) / before * 100", "%", _decrement, _under(5)),
    "post_high_intensity_max_force_decrement": _TargetSpec("≤5%", ("before_value", "after_value"), "(before-after) / before * 100", "%", _decrement, _under(5)),
    "post_high_intensity_explosive_power_decrement": _TargetSpec("≤8%", ("before_value", "after_value"), "(before-after) / before * 100", "%", _decrement, _under(8)),
    "vo2max": _TargetSpec("60–70 ml/kg/min", ("oxygen_consumption_ml_min", "body_mass_kg"), "oxygen_consumption_ml_min / body_mass_kg", "ml/kg/min", _vo2max, _over(60)),
    "heart_rate_recovery_1min": _TargetSpec("≥40–50 bpm 감소", ("exercise_end_bpm", "heart_rate_1min_bpm"), "exercise_end_bpm - heart_rate_1min_bpm", "bpm", _hrr, _over(40)),
    "annual_training_adherence": _TargetSpec("≥95%/년", ("completed_sessions", "planned_sessions"), "completed_sessions / planned_sessions * 100", "%", _adherence, _over(95), evidence_class=CalculationEvidenceClass.EXACT),
    "major_injury_count": _TargetSpec("0회", ("major_injury_count",), "major_injury_count", "count", _direct("major_injury_count", "count"), lambda value: value == 0),
}


def calculate_target(request: TargetCalculationRequest) -> TargetCalculationResult:
    try:
        spec = TARGET_SPECS[request.target_id]
    except KeyError as exc:
        raise ValueError(f"unknown physical target: {request.target_id}") from exc
    missing = tuple(name for name in spec.required if name not in request.inputs)
    base = dict(
        target_id=request.target_id,
        target=spec.target,
        formula_id=f"physical-target:{request.target_id}",
        evidence_class=spec.evidence_class,
        required_inputs=spec.required,
        input_hash=canonical_sha256(request),
    )
    if missing:
        return TargetCalculationResult(
            **base,
            status=CalculationStatus.INPUT_REQUIRED,
            missing_inputs=missing,
            details={"required_units": {name: "method-specific; call with all inputs to validate" for name in spec.required}},
        )
    value, details = spec.compute(request)
    if not math.isfinite(value):
        raise ValueError("calculation produced a non-finite value")
    return TargetCalculationResult(
        **base,
        status=CalculationStatus.CALCULATED,
        value=value,
        unit=spec.unit,
        meets_target_floor=spec.meets(value),
        formula=spec.formula,
        details=details,
    )


__all__ = [name for name in globals() if not name.startswith("_")]
