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
import tempfile
import struct
from importlib import metadata
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
    preserved_path: str | None = None


class ExternalEngineReceipt(ScientificModel):
    component_id: NonEmptyStr
    runtime_path: NonEmptyStr
    arguments: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    inputs: tuple[ArtifactReceipt, ...]
    outputs: tuple[ArtifactReceipt, ...]
    execution_manifest: dict[str, object] = Field(default_factory=dict)


class ExternalEngineFailure(ScientificModel):
    component_id: NonEmptyStr
    runtime_path: NonEmptyStr
    arguments: tuple[str, ...]
    inputs: tuple[ArtifactReceipt, ...]
    exit_code: int | None = None
    timeout_seconds: int | None = None
    stdout: str = ""
    stderr: str = ""


class ExternalEngineError(RuntimeError):
    def __init__(self, message: str, receipt: ExternalEngineFailure) -> None:
        super().__init__(message)
        self.receipt = receipt


def _receipt(path: Path, *, preserve_under: Path | None = None) -> ArtifactReceipt:
    if not path.is_file():
        raise FileNotFoundError(f"required external-engine artifact is absent: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    sha256 = digest.hexdigest()
    preserved = None
    if preserve_under is not None:
        destination = preserve_under / sha256 / path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            temporary: str | None = None
            try:
                with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as target:
                    temporary = target.name
                    copied = hashlib.sha256()
                    with path.open("rb") as source:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            copied.update(chunk)
                            target.write(chunk)
                if copied.hexdigest() != sha256:
                    raise ValueError("artifact changed while being preserved")
                os.replace(temporary, destination)
                temporary = None
            finally:
                if temporary is not None:
                    Path(temporary).unlink(missing_ok=True)
        if _receipt(destination).sha256 != sha256:
            raise ValueError("preserved artifact content hash mismatch")
        preserved = str(destination.resolve())
    return ArtifactReceipt(path=str(path.resolve()), sha256=sha256,
                           size_bytes=path.stat().st_size, preserved_path=preserved)


def verified_artifact_path(artifact: ArtifactReceipt) -> Path:
    """Read the preserved bytes when available, and detect stale legacy paths."""
    path = Path(artifact.preserved_path or artifact.path)
    actual = _receipt(path)
    if actual.sha256 != artifact.sha256 or actual.size_bytes != artifact.size_bytes:
        raise ValueError("external-engine artifact no longer matches its receipt")
    return path


def _execution_manifest(root: Path, runtime_path: str) -> dict[str, object]:
    packages = {}
    for name in ("pydantic", "numpy", "cobra", "opensim"):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pass
    runtime = Path(runtime_path)
    lock = root / "uv.lock"
    return {"host_python": sys.version, "host_platform": sys.platform,
            "host_pointer_bits": 8 * struct.calcsize("P"),
            "host_packages": packages,
            "workspace_lock_sha256": _receipt(lock).sha256 if lock.is_file() else None,
            "runtime_sha256": _receipt(runtime).sha256 if runtime.is_file() else None,
            "boundary": "Host packages do not describe a separately registered engine's internal environment."}


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
        def workspace_path(path: str) -> Path:
            resolved = root.joinpath(path).resolve()
            if resolved != root and root not in resolved.parents:
                raise ValueError("external-engine artifacts must stay inside workspace")
            return resolved
        input_paths = tuple(workspace_path(path) for path in job.input_artifacts)
        output_paths = tuple(workspace_path(path) for path in job.expected_output_artifacts)
        artifact_root = root / ".research-artifacts" / "sha256"
        inputs = tuple(_receipt(path, preserve_under=artifact_root) for path in input_paths)
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
        failure_context = {
            "component_id": job.component_id, "runtime_path": component.runtime_path,
            "arguments": runtime_arguments, "inputs": inputs,
        }
        try:
            completed = subprocess.run(
                command, cwd=working_directory, shell=False, env=environment,
                capture_output=True, text=False, timeout=job.timeout_seconds, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ExternalEngineError(
                f"{job.component_id} timed out after {job.timeout_seconds}s",
                ExternalEngineFailure(**failure_context, timeout_seconds=job.timeout_seconds,
                    stdout=_decode_process_output(exc.stdout), stderr=_decode_process_output(exc.stderr)),
            ) from exc
        except OSError as exc:
            raise ExternalEngineError(str(exc), ExternalEngineFailure(**failure_context)) from exc
        stdout = _decode_process_output(completed.stdout)
        stderr = _decode_process_output(completed.stderr)
        if completed.returncode != 0:
            diagnostic = "\n".join(
                part for part in (stdout.strip(), stderr.strip()) if part
            )
            raise ExternalEngineError(
                f"{job.component_id} failed with exit code {completed.returncode}: "
                f"{diagnostic[-4000:] or 'engine returned no diagnostic output'}",
                ExternalEngineFailure(**failure_context, exit_code=completed.returncode,
                    stdout=stdout, stderr=stderr),
            )
        try:
            outputs = tuple(_receipt(path, preserve_under=artifact_root) for path in output_paths)
        except (OSError, ValueError) as exc:
            raise ExternalEngineError(str(exc), ExternalEngineFailure(
                **failure_context, exit_code=completed.returncode, stdout=stdout, stderr=stderr,
            )) from exc
        return ExternalEngineReceipt(
            component_id=job.component_id, runtime_path=component.runtime_path,
            arguments=runtime_arguments, exit_code=completed.returncode,
            stdout=stdout, stderr=stderr,
            inputs=inputs, outputs=outputs,
            execution_manifest=_execution_manifest(root, str(component.runtime_path)),
        )


__all__ = ["ArtifactReceipt", "ExternalEngineJob", "ExternalEngineReceipt", "ExternalEngineRunner", "verified_artifact_path"]
