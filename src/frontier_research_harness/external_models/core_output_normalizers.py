"""Deterministic normalization for typed OpenSim, Pulse, and FEBio runs.

Normalization exposes traceable observables only.  It does not convert a
reference run into a personal endpoint or infer biological adaptation.
"""
from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from typing import Any

from frontier_research_harness.scientific_contracts import canonical_sha256

from .external_engine_runner import ExternalEngineReceipt, verified_artifact_path


def _magnitude(values: list[float]) -> float:
    return math.sqrt(sum(float(value) ** 2 for value in values))


def normalize_opensim(receipt: ExternalEngineReceipt) -> dict[str, Any]:
    try:
        payload = json.loads(receipt.stdout.strip())
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("typed OpenSim output must be one JSON object on stdout") from exc
    if isinstance(payload, dict) and payload.get("observable_kind") == "JOINT_REACTION_SERIES":
        return normalize_opensim_series(payload)
    required = {"joint", "side", "time_seconds", "force_n", "moment_nm", "state_kind"}
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError("typed OpenSim output missing: " + ", ".join(missing))
    force = [float(value) for value in payload["force_n"]]
    moment = [float(value) for value in payload["moment_nm"]]
    if len(force) != 3 or len(moment) != 3:
        raise ValueError("OpenSim force and moment outputs must have three components")
    return {
        "observable_kind": "JOINT_REACTION_SNAPSHOT",
        "joint": payload["joint"], "side": payload["side"],
        "time_seconds": float(payload["time_seconds"]),
        "force_n": force, "force_magnitude_n": _magnitude(force),
        "moment_nm": moment, "moment_magnitude_nm": _magnitude(moment),
        "state_kind": payload["state_kind"],
        "applied_state_variable_values": payload.get("applied_state_variable_values", {}),
        "limitations": [
            "A single joint-reaction snapshot is not CMJ performance, injury probability, or longitudinal adaptation.",
        ],
    }


def normalize_opensim_series(payload: dict[str, Any]) -> dict[str, Any]:
    def number(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("OpenSim series values must be finite numeric scalars")
        return float(value)
    rows = payload.get("samples")
    if not isinstance(rows, list) or not 2 <= len(rows) <= 10000:
        raise ValueError("OpenSim series requires 2 to 10000 samples")
    if payload.get("side") not in {"child", "parent"} or payload.get("expressed_in_frame") != "ground" or not payload.get("joint"):
        raise ValueError("OpenSim series must declare joint, side and ground frame")
    samples = []
    for row in rows:
        force, moment = [number(v) for v in row["force_n"]], [number(v) for v in row["moment_nm"]]
        if len(force) != 3 or len(moment) != 3:
            raise ValueError("OpenSim series vectors must have three components")
        samples.append({"time_seconds": number(row["time_seconds"]), "force_n": force, "moment_nm": moment,
                        "force_magnitude_n": number(math.hypot(*force)), "moment_magnitude_nm": number(math.hypot(*moment))})
    if any(b["time_seconds"] <= a["time_seconds"] for a, b in zip(samples, samples[1:])):
        raise ValueError("OpenSim series times must be strictly increasing")
    duration = number(samples[-1]["time_seconds"] - samples[0]["time_seconds"])
    integral = number(sum((b["time_seconds"] - a["time_seconds"]) *
                         (a["force_magnitude_n"] / 2 + b["force_magnitude_n"] / 2)
                         for a, b in zip(samples, samples[1:])))
    return {"observable_kind": "JOINT_REACTION_SERIES", "joint": payload["joint"], "side": payload["side"],
            "expressed_in_frame": "ground", "samples": samples, "sample_count": len(samples),
            "duration_seconds": duration, "peak_force_n": max(s["force_magnitude_n"] for s in samples),
            "peak_moment_nm": max(s["moment_magnitude_nm"] for s in samples),
            "force_magnitude_integral_ns": integral, "time_mean_force_n": number(integral / duration),
            "aggregation": "Trapezoidal integral between supplied samples; magnitude integral is not vector impulse.",
            "limitations": ["States evaluated independently; this does not establish a dynamically consistent movement.",
                            "Sampled peaks may miss intervening peaks. No growth, injury probability or personal performance forecast."]}


def _finite_float(value: str) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def normalize_pulse(
    receipt: ExternalEngineReceipt, *, exercise_end_seconds: float | None = None,
    recovery_interval_seconds: float = 60.0,
) -> dict[str, Any]:
    if not math.isfinite(recovery_interval_seconds) or recovery_interval_seconds <= 0:
        raise ValueError("recovery_interval_seconds must be finite and positive")
    if exercise_end_seconds is not None and (
        not math.isfinite(exercise_end_seconds) or exercise_end_seconds < 0
    ):
        raise ValueError("exercise_end_seconds must be finite and non-negative")
    if len(receipt.outputs) != 1:
        raise ValueError("typed Pulse study requires exactly one declared results CSV")
    path = verified_artifact_path(receipt.outputs[0])
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or "Time(s)" not in rows[0]:
        raise ValueError("Pulse results must contain rows and a Time(s) column")
    columns = {
        "heart_rate_bpm": "HeartRate(1/min)",
        "oxygen_consumption_ml_min": "OxygenConsumptionRate(mL/min)",
        "total_metabolic_rate_w": "TotalMetabolicRate(W)",
        "achieved_exercise_level": "AchievedExerciseLevel",
    }
    time_series: list[tuple[float, dict[str, float | None]]] = []
    for row in rows:
        time_value = _finite_float(row.get("Time(s)", ""))
        if time_value is None:
            continue
        time_series.append((time_value, {name: _finite_float(row.get(column, "")) for name, column in columns.items()}))
    if not time_series:
        raise ValueError("Pulse results contain no finite time values")
    if any(right[0] <= left[0] for left, right in zip(time_series, time_series[1:])):
        raise ValueError("Pulse sample times must be strictly increasing")
    summaries: dict[str, dict[str, float]] = {}
    for name in columns:
        values = [item[name] for _, item in time_series if item[name] is not None]
        if values:
            summaries[name] = {"minimum": min(values), "maximum": max(values), "final": values[-1]}
    heart_rate_recovery = None
    recovery_status = "EXERCISE_END_NOT_SUPPLIED"
    if exercise_end_seconds is not None:
        recovery_time = exercise_end_seconds + recovery_interval_seconds
        def exact_sample(target: float) -> tuple[float, dict[str, float | None]] | None:
            return next((item for item in time_series if math.isclose(
                item[0], target, rel_tol=0, abs_tol=1e-6
            )), None)
        end = exact_sample(exercise_end_seconds)
        recovered = exact_sample(recovery_time)
        recovery_status = (
            "OUTSIDE_RECORDED_HORIZON"
            if exercise_end_seconds < time_series[0][0] or recovery_time > time_series[-1][0] + 1e-6
            else "REQUESTED_SAMPLE_NOT_PRESENT"
        )
        if end is not None and recovered is not None and recovered[0] > end[0]:
            recovery_status = "HEART_RATE_MISSING"
        if (end is not None and recovered is not None and recovered[0] > end[0]
                and end[1]["heart_rate_bpm"] is not None
                and recovered[1]["heart_rate_bpm"] is not None):
            heart_rate_recovery = {
                "exercise_end_sample_seconds": end[0],
                "recovery_sample_seconds": recovered[0],
                "decrease_bpm": end[1]["heart_rate_bpm"] - recovered[1]["heart_rate_bpm"],
            }
            recovery_status = "EXACT_SAMPLES"
    return {
        "observable_kind": "PULSE_SCENARIO_TIME_SERIES_SUMMARY",
        "row_count": len(time_series), "start_seconds": time_series[0][0],
        "end_seconds": time_series[-1][0], "columns": summaries,
        "heart_rate_recovery": heart_rate_recovery,
        "heart_rate_recovery_status": recovery_status,
        "results_sha256": receipt.outputs[0].sha256,
        "limitations": [
            "Peak simulated oxygen consumption is not a measured personal VO2max.",
            "Heart-rate recovery is exposed only when the caller declares the exercise-end time.",
            "Both requested time samples must exist; no nearest-endpoint substitution or implicit interpolation is used.",
        ],
    }


def normalize_febio(receipt: ExternalEngineReceipt) -> dict[str, Any]:
    log_receipt = next((item for item in receipt.outputs if item.path.lower().endswith(".log")), None)
    if log_receipt is None:
        raise ValueError("typed FEBio study requires a declared log output")
    text = verified_artifact_path(log_receipt).read_text(encoding="utf-8", errors="replace")
    steps = re.search(r"Number of time steps completed\s*\.*\s*:\s*(\d+)", text)
    times = re.findall(r"converged at time\s*:\s*([-+0-9.eE]+)", text)
    normal = "N O R M A L   T E R M I N A T I O N" in text
    return {
        "observable_kind": "FEBIO_SOLVER_SUMMARY",
        "normal_termination": normal,
        "completed_time_steps": int(steps.group(1)) if steps else None,
        "final_simulation_time": float(times[-1]) if times else None,
        "log_sha256": log_receipt.sha256,
        "declared_output_hashes": {Path(item.path).name: item.sha256 for item in receipt.outputs},
        "content_hash": canonical_sha256({"normal": normal, "steps": steps.group(1) if steps else None, "times": times}),
        "limitations": [
            "Solver convergence is not anatomical validation or injury probability.",
            "Stress, strain, and damage observables require a study-specific FEBio data export and are not inferred from an XPLT hash.",
        ],
    }


__all__ = ["normalize_febio", "normalize_opensim", "normalize_pulse"]
