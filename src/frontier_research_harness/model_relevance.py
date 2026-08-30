"""Deterministic target-to-model routing metadata.

This module does not choose a scientific question or a winning model.  It only
prevents a result from one physiological scale being presented as coverage of
an unrelated goal target.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Iterable


class ModelLayer(StrEnum):
    WHOLE_PERSON_PHYSIOLOGY = "whole_person_physiology"
    ORGAN_CIRCULATION = "organ_circulation"
    MUSCULOSKELETAL_MECHANICS = "musculoskeletal_mechanics"
    TISSUE_DURABILITY = "tissue_durability"
    CELLULAR_METABOLISM = "cellular_metabolism"


MODEL_LAYER_ORDER = tuple(ModelLayer)

MODEL_RESEARCH_LAYERS: dict[str, ModelLayer] = {
    "pulse": ModelLayer.WHOLE_PERSON_PHYSIOLOGY,
    "hummod": ModelLayer.WHOLE_PERSON_PHYSIOLOGY,
    "circadapt": ModelLayer.ORGAN_CIRCULATION,
    "opensim": ModelLayer.MUSCULOSKELETAL_MECHANICS,
    "moco": ModelLayer.MUSCULOSKELETAL_MECHANICS,
    "myosuite": ModelLayer.MUSCULOSKELETAL_MECHANICS,
    "febio": ModelLayer.TISSUE_DURABILITY,
    "human_gem": ModelLayer.CELLULAR_METABOLISM,
    "mitocore": ModelLayer.CELLULAR_METABOLISM,
    "mitochondria_qsp": ModelLayer.CELLULAR_METABOLISM,
}

MODEL_TARGET_CANDIDATES: dict[str, tuple[str, ...]] = {
    "opensim": (
        "imtp_peak_force", "rfd_0_50_ms", "rfd_0_250_ms", "cmj_height",
        "cmj_relative_peak_power", "cmj_absolute_peak_power",
        "dynamic_balance_asymmetry", "whole_body_force_power_asymmetry",
        "fatigued_dynamic_joint_stability_decrement",
    ),
    "moco": (
        "rfd_0_50_ms", "rfd_0_250_ms", "cmj_height",
        "cmj_relative_peak_power", "cmj_absolute_peak_power",
        "dynamic_balance_asymmetry",
    ),
    "myosuite": (
        "imtp_peak_force", "rfd_0_50_ms", "rfd_0_250_ms",
        "dynamic_balance_asymmetry", "fatigued_dynamic_joint_stability_decrement",
    ),
    "febio": ("fatigued_dynamic_joint_stability_decrement", "major_injury_count"),
    "pulse": (
        "vo2max", "heart_rate_recovery_1min",
        "post_high_intensity_max_force_decrement",
        "post_high_intensity_explosive_power_decrement",
    ),
    "circadapt": ("vo2max", "heart_rate_recovery_1min"),
    "human_gem": (
        "wingate_peak_power", "wingate_mean_power",
        "repeated_explosive_output_decrement",
    ),
    "mitocore": (
        "wingate_peak_power", "wingate_mean_power",
        "repeated_explosive_output_decrement",
    ),
    "mitochondria_qsp": (
        "wingate_peak_power", "wingate_mean_power",
        "repeated_explosive_output_decrement",
        "post_high_intensity_explosive_power_decrement",
    ),
}


# These are runnable, already-receipted reference boundaries.  They are exposed
# to Codex as recovery inputs, never as personalized or longitudinal forecasts.
MODEL_REFERENCE_EXPERIMENTS: dict[str, dict[str, object]] = {
    "pulse": {
        "input": {
            "arguments": ["scripts/external_engines/pulse_exercise_smoke.json"],
            "input_artifacts": ["scripts/external_engines/pulse_exercise_smoke.json"],
            "working_directory": ".scratch/pulse-ascii/install/bin",
            "timeout_seconds": 300,
        },
        "boundary": "Generic 60-second Pulse exercise/recovery execution check; not VO2max, HRR, adaptation, or a personal forecast.",
    },
    "circadapt": {
        "input": {
            "arguments": ["scripts/external_engines/circadapt_smoke.py"],
            "input_artifacts": ["scripts/external_engines/circadapt_smoke.py"],
            "timeout_seconds": 300,
        },
        "boundary": "Bundled reference circulation only; not training adaptation.",
    },
    "opensim": {
        "input": {
            "arguments": [
                "scripts/external_engines/opensim_joint_reaction.py",
                "--model",
                "vendor/opensim-core/Applications/Scale/tests/resources/gait2354_simbody.osim",
                "--joint",
                "knee_r",
                "--side",
                "child",
            ],
            "input_artifacts": [
                "scripts/external_engines/opensim_joint_reaction.py",
                "vendor/opensim-core/Applications/Scale/tests/resources/gait2354_simbody.osim",
            ],
            "timeout_seconds": 300,
        },
        "boundary": "Generic model default-state joint reaction; personal motion and scaling remain required.",
    },
    "moco": {
        "input": {
            "arguments": ["scripts/external_engines/moco_smoke.py"],
            "input_artifacts": ["scripts/external_engines/moco_smoke.py"],
            "timeout_seconds": 300,
        },
        "boundary": "Abstract minimum-time control boundary; not a CMJ or personal movement prediction.",
    },
    "febio": {
        "input": {
            "arguments": ["Model1.feb"],
            "input_artifacts": [".scratch/FEBioUncertainSCI/Model1.feb"],
            "working_directory": ".scratch/FEBioUncertainSCI",
            "timeout_seconds": 300,
        },
        "boundary": "Public uniaxial material case; not an anatomical injury forecast.",
    },
}


def model_layer(model_name: str) -> ModelLayer | None:
    return MODEL_RESEARCH_LAYERS.get(model_name)


def candidate_targets(model_name: str) -> tuple[str, ...]:
    return MODEL_TARGET_CANDIDATES.get(model_name, ())


def required_layers(
    target_ids: Iterable[str], *, available_model_ids: Iterable[str] | None = None
) -> tuple[ModelLayer, ...]:
    targets = {str(item) for item in target_ids}
    available = None if available_model_ids is None else set(available_model_ids)
    required = {
        layer
        for name, layer in MODEL_RESEARCH_LAYERS.items()
        if (available is None or name in available)
        and targets.intersection(MODEL_TARGET_CANDIDATES.get(name, ()))
    }
    return tuple(layer for layer in MODEL_LAYER_ORDER if layer in required)


def relevant_models_by_layer(
    target_ids: Iterable[str], *, available_model_ids: Iterable[str] | None = None
) -> dict[str, list[str]]:
    targets = {str(item) for item in target_ids}
    available = None if available_model_ids is None else set(available_model_ids)
    result: dict[str, list[str]] = {}
    for name, layer in MODEL_RESEARCH_LAYERS.items():
        if available is not None and name not in available:
            continue
        if not targets.intersection(MODEL_TARGET_CANDIDATES.get(name, ())):
            continue
        result.setdefault(layer.value, []).append(name)
    return result


__all__ = [name for name in globals() if not name.startswith("_")]
