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

from .external_engine_runner import ExternalEngineReceipt


def _magnitude(values: list[float]) -> float:
    return math.sqrt(sum(float(value) ** 2 for value in values))


def normalize_opensim(receipt: ExternalEngineReceipt) -> dict[str, Any]:
    try:
        payload = json.loads(receipt.stdout.strip())
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("typed OpenSim output must be one JSON object on stdout") from exc
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
    if len(receipt.outputs) != 1:
        raise ValueError("typed Pulse study requires exactly one declared results CSV")
    path = Path(receipt.outputs[0].path)
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
    summaries: dict[str, dict[str, float]] = {}
    for name in columns:
        values = [item[name] for _, item in time_series if item[name] is not None]
        if values:
            summaries[name] = {"minimum": min(values), "maximum": max(values), "final": values[-1]}
    heart_rate_recovery = None
    if exercise_end_seconds is not None:
        def nearest(target: float) -> tuple[float, dict[str, float | None]]:
            return min(time_series, key=lambda item: abs(item[0] - target))
        end = nearest(exercise_end_seconds)
        recovered = nearest(exercise_end_seconds + recovery_interval_seconds)
        if end[1]["heart_rate_bpm"] is not None and recovered[1]["heart_rate_bpm"] is not None:
            heart_rate_recovery = {
                "exercise_end_sample_seconds": end[0],
                "recovery_sample_seconds": recovered[0],
                "decrease_bpm": end[1]["heart_rate_bpm"] - recovered[1]["heart_rate_bpm"],
            }
    return {
        "observable_kind": "PULSE_SCENARIO_TIME_SERIES_SUMMARY",
        "row_count": len(time_series), "start_seconds": time_series[0][0],
        "end_seconds": time_series[-1][0], "columns": summaries,
        "heart_rate_recovery": heart_rate_recovery,
        "results_sha256": receipt.outputs[0].sha256,
        "limitations": [
            "Peak simulated oxygen consumption is not a measured personal VO2max.",
            "Heart-rate recovery is exposed only when the caller declares the exercise-end time.",
        ],
    }


def normalize_febio(receipt: ExternalEngineReceipt) -> dict[str, Any]:
    log_receipt = next((item for item in receipt.outputs if item.path.lower().endswith(".log")), None)
    if log_receipt is None:
        raise ValueError("typed FEBio study requires a declared log output")
    text = Path(log_receipt.path).read_text(encoding="utf-8", errors="replace")
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
