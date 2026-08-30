"""Typed, fail-closed jobs for the highest-priority external engines.

The contracts translate a scientific study request into the existing process
boundary.  They do not select a question, invent subject data, or interpret an
engine result.
"""
from __future__ import annotations

from enum import StrEnum
from pathlib import PurePosixPath

from pydantic import Field, model_validator

from frontier_research_harness.scientific_contracts import NonEmptyStr, ScientificModel

from .external_engine_runner import ExternalEngineJob


class CalibrationBoundary(StrEnum):
    REFERENCE = "REFERENCE"
    PERSONAL_OBSERVATION = "PERSONAL_OBSERVATION"


def _workspace_path(value: str, field: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field} must be a workspace-relative path")
    return str(path)


class OpenSimJointReactionStudy(ScientificModel):
    study_type: str = "joint_reaction"
    model_path: NonEmptyStr
    joint: NonEmptyStr
    side: str
    state_snapshot_path: str | None = None
    calibration: CalibrationBoundary
    timeout_seconds: int = Field(default=300, ge=1, le=3600)

    @model_validator(mode="after")
    def validate_study(self) -> "OpenSimJointReactionStudy":
        if self.study_type != "joint_reaction":
            raise ValueError("OpenSim study_type must be 'joint_reaction'")
        if self.side not in {"child", "parent"}:
            raise ValueError("OpenSim side must be 'child' or 'parent'")
        _workspace_path(self.model_path, "model_path")
        if self.state_snapshot_path is not None:
            _workspace_path(self.state_snapshot_path, "state_snapshot_path")
        if self.calibration is CalibrationBoundary.PERSONAL_OBSERVATION and self.state_snapshot_path is None:
            raise ValueError("personal OpenSim studies require state_snapshot_path")
        return self

    def to_job(self) -> ExternalEngineJob:
        driver = "scripts/external_engines/opensim_joint_reaction.py"
        arguments = [driver, "--model", self.model_path, "--joint", self.joint, "--side", self.side]
        artifacts = [driver, self.model_path]
        if self.state_snapshot_path:
            arguments.extend(["--state-snapshot", self.state_snapshot_path])
            artifacts.append(self.state_snapshot_path)
        return ExternalEngineJob(
            component_id="opensim", arguments=tuple(arguments),
            input_artifacts=tuple(artifacts), timeout_seconds=self.timeout_seconds,
        )


class PulseScenarioStudy(ScientificModel):
    study_type: str = "scenario"
    scenario_path: NonEmptyStr
    expected_results_path: NonEmptyStr
    working_directory: NonEmptyStr = ".scratch/pulse-ascii/install/bin"
    calibration: CalibrationBoundary
    exercise_end_seconds: float | None = Field(default=None, ge=0)
    recovery_interval_seconds: float = Field(default=60.0, gt=0, le=600)
    timeout_seconds: int = Field(default=900, ge=1, le=7200)

    @model_validator(mode="after")
    def validate_study(self) -> "PulseScenarioStudy":
        if self.study_type != "scenario":
            raise ValueError("Pulse study_type must be 'scenario'")
        _workspace_path(self.scenario_path, "scenario_path")
        _workspace_path(self.expected_results_path, "expected_results_path")
        _workspace_path(self.working_directory, "working_directory")
        return self

    def to_job(self) -> ExternalEngineJob:
        return ExternalEngineJob(
            component_id="pulse", arguments=(self.scenario_path,),
            input_artifacts=(self.scenario_path,),
            expected_output_artifacts=(self.expected_results_path,),
            working_directory=self.working_directory,
            timeout_seconds=self.timeout_seconds,
        )


class FebioStudy(ScientificModel):
    study_type: str = "finite_element"
    model_path: NonEmptyStr
    expected_log_path: NonEmptyStr
    expected_plot_path: str | None = None
    calibration: CalibrationBoundary
    timeout_seconds: int = Field(default=1800, ge=1, le=14_400)

    @model_validator(mode="after")
    def validate_study(self) -> "FebioStudy":
        if self.study_type != "finite_element":
            raise ValueError("FEBio study_type must be 'finite_element'")
        _workspace_path(self.model_path, "model_path")
        _workspace_path(self.expected_log_path, "expected_log_path")
        if self.expected_plot_path:
            _workspace_path(self.expected_plot_path, "expected_plot_path")
        return self

    def to_job(self) -> ExternalEngineJob:
        model = PurePosixPath(self.model_path)
        outputs = [self.expected_log_path]
        if self.expected_plot_path:
            outputs.append(self.expected_plot_path)
        return ExternalEngineJob(
            component_id="febio", arguments=(model.name,),
            input_artifacts=(self.model_path,), expected_output_artifacts=tuple(outputs),
            working_directory=str(model.parent), timeout_seconds=self.timeout_seconds,
        )


CORE_STUDY_CONTRACTS = {
    "opensim": OpenSimJointReactionStudy,
    "pulse": PulseScenarioStudy,
    "febio": FebioStudy,
}


__all__ = [name for name in globals() if not name.startswith("_")]
