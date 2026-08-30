"""Process boundary for connected external scientific engines.

This module deliberately contains no physiological equations.  It executes
only a runtime discovered by the federation inventory and records exact
artifacts and process output for later scientific interpretation.
"""
from __future__ import annotations

import hashlib
import locale
import os
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path

from pydantic import Field, model_validator

from frontier_research_harness.scientific_contracts import NonEmptyStr, ScientificModel

from .external_engine_federation import ConnectionStatus, external_federation_inventory


class ExternalEngineJob(ScientificModel):
    component_id: NonEmptyStr
    arguments: tuple[str, ...] = ()
    input_artifacts: tuple[NonEmptyStr, ...] = ()
    expected_output_artifacts: tuple[NonEmptyStr, ...] = ()
    working_directory: str | None = None
    timeout_seconds: int = Field(default=3600, ge=1, le=86_400)

    @model_validator(mode="after")
    def arguments_are_data_only(self) -> "ExternalEngineJob":
        if any("\x00" in item for item in self.arguments):
            raise ValueError("engine arguments cannot contain NUL")
        return self


class ArtifactReceipt(ScientificModel):
    path: NonEmptyStr
    sha256: NonEmptyStr
    size_bytes: int = Field(ge=0)


class ExternalEngineReceipt(ScientificModel):
    component_id: NonEmptyStr
    runtime_path: NonEmptyStr
    arguments: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    inputs: tuple[ArtifactReceipt, ...]
    outputs: tuple[ArtifactReceipt, ...]


def _receipt(path: Path) -> ArtifactReceipt:
    if not path.is_file():
        raise FileNotFoundError(f"required external-engine artifact is absent: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return ArtifactReceipt(path=str(path.resolve()), sha256=digest.hexdigest(), size_bytes=path.stat().st_size)


def _decode_process_output(payload: bytes | str | None) -> str:
    """Decode native-engine output without assuming one Windows code page."""
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    encodings = ("utf-8", locale.getencoding())
    for encoding in dict.fromkeys(encodings):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode(encodings[-1], errors="replace")


class ExternalEngineRunner:
    """Run one registered executable without a shell or internal fallback."""

    @staticmethod
    def _isolated_native_environment() -> dict[str, str]:
        """Keep a registered engine independent from Codex's Python runtime.

        Windows virtual environments commonly export PYTHONPATH/PYTHONHOME from
        the harness interpreter.  A registered engine may embed or launch a
        different Python version, so inheriting those paths can load ABI-
        incompatible packages before the engine itself starts.
        """
        environment = os.environ.copy()
        for variable in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX"):
            environment.pop(variable, None)
        return environment

    @staticmethod
    def _command_and_environment(component: object, arguments: tuple[str, ...]) -> tuple[list[str], dict[str, str] | None]:
        runtime_path = str(getattr(component, "runtime_path"))
        if not runtime_path.startswith("python:"):
            return [runtime_path, *arguments], ExternalEngineRunner._isolated_native_environment()
        module_name = runtime_path.split(":", 1)[1]
        spec = find_spec(module_name)
        if spec is None:
            raise RuntimeError(
                f"registered Python module is not importable in this runtime: {module_name}"
            )
        if not arguments:
            raise ValueError(
                f"{getattr(component, 'component_id')} requires a registered Python driver script argument"
            )
        environment = os.environ.copy()
        if getattr(component, "component_id") == "moco" and spec.origin:
            environment["CASADIPATH"] = str(Path(spec.origin).resolve().parent)
        return [sys.executable, *arguments], environment

    def run(self, job: ExternalEngineJob, *, workspace_root: str | Path | None = None) -> ExternalEngineReceipt:
        root = Path(workspace_root or Path.cwd()).resolve()
        inventory = external_federation_inventory(root)
        component = next((item for item in inventory.components if item.component_id == job.component_id), None)
        if component is None:
            raise ValueError(f"unknown federation component: {job.component_id}")
        if component.status is not ConnectionStatus.READY or not component.runtime_path:
            raise RuntimeError(f"external runtime is not ready: {job.component_id} ({component.status})")
        inputs = tuple(_receipt(root.joinpath(path)) for path in job.input_artifacts)
        working_directory = root.joinpath(job.working_directory or ".").resolve()
        if working_directory != root and root not in working_directory.parents:
            raise ValueError("external-engine working directory must stay inside workspace")
        if not working_directory.is_dir():
            raise FileNotFoundError(f"external-engine working directory is absent: {working_directory}")
        declared_inputs = {
            path: str(root.joinpath(path).resolve()) for path in job.input_artifacts
        }
        runtime_arguments = tuple(
            declared_inputs.get(argument, argument) for argument in job.arguments
        )
        command, environment = self._command_and_environment(component, runtime_arguments)
        completed = subprocess.run(
            command, cwd=working_directory, shell=False, env=environment,
            capture_output=True, text=False, timeout=job.timeout_seconds, check=False,
        )
        stdout = _decode_process_output(completed.stdout)
        stderr = _decode_process_output(completed.stderr)
        if completed.returncode != 0:
            diagnostic = "\n".join(
                part for part in (stdout.strip(), stderr.strip()) if part
            )
            raise RuntimeError(
                f"{job.component_id} failed with exit code {completed.returncode}: "
                f"{diagnostic[-4000:] or 'engine returned no diagnostic output'}"
            )
        outputs = tuple(_receipt(root.joinpath(path)) for path in job.expected_output_artifacts)
        return ExternalEngineReceipt(
            component_id=job.component_id, runtime_path=component.runtime_path,
            arguments=runtime_arguments, exit_code=completed.returncode,
            stdout=stdout[-20_000:], stderr=stderr[-20_000:],
            inputs=inputs, outputs=outputs,
        )


__all__ = ["ArtifactReceipt", "ExternalEngineJob", "ExternalEngineReceipt", "ExternalEngineRunner"]
