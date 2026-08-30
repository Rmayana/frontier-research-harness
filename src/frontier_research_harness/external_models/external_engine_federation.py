"""Fail-closed inventory for connected external scientific models.

Source code, a model catalogue, or a reference architecture is never reported
as an executable engine.  An engine becomes READY only when its runtime can be
located; experiment-specific model files and smoke tests are additional gates.
"""
from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from importlib.util import find_spec
from pathlib import Path
from shutil import which

from pydantic import Field

from frontier_research_harness.scientific_contracts import NonEmptyStr, ScientificModel


class FederationRole(StrEnum):
    EXECUTION_ENGINE = "EXECUTION_ENGINE"
    LICENSED_ENGINE = "LICENSED_ENGINE"
    MODEL_ASSET = "MODEL_ASSET"
    DATA_KNOWLEDGE = "DATA_KNOWLEDGE"
    ORCHESTRATION_REFERENCE = "ORCHESTRATION_REFERENCE"
    ARCHITECTURE_REFERENCE = "ARCHITECTURE_REFERENCE"


class ConnectionStatus(StrEnum):
    READY = "READY"
    RUNTIME_UNVERIFIED = "RUNTIME_UNVERIFIED"
    SOURCE_ONLY = "SOURCE_ONLY"
    RUNTIME_MISSING = "RUNTIME_MISSING"
    LICENSE_REQUIRED = "LICENSE_REQUIRED"
    MODEL_ASSET_REQUIRED = "MODEL_ASSET_REQUIRED"
    MODEL_ASSET_READY = "MODEL_ASSET_READY"
    REFERENCE_ONLY = "REFERENCE_ONLY"


class ExternalComponent(ScientificModel):
    component_id: NonEmptyStr
    name: NonEmptyStr
    layer: NonEmptyStr
    role: FederationRole
    status: ConnectionStatus
    runtime_path: str | None = None
    source_path: str | None = None
    required_inputs: tuple[NonEmptyStr, ...] = ()
    declared_outputs: tuple[NonEmptyStr, ...] = ()
    blockers: tuple[NonEmptyStr, ...] = ()


class FederationInventory(ScientificModel):
    federation_id: NonEmptyStr = "external-human-federation-v1"
    components: tuple[ExternalComponent, ...] = Field(min_length=1)
    executable_component_ids: tuple[NonEmptyStr, ...]
    ready_for_execution: bool
    blocking_component_ids: tuple[NonEmptyStr, ...]


class RuntimeRegistration(ScientificModel):
    component_id: NonEmptyStr
    path: NonEmptyStr
    sha256: NonEmptyStr


class RuntimeManifest(ScientificModel):
    schema_version: NonEmptyStr
    runtimes: tuple[RuntimeRegistration, ...]

    @property
    def by_component(self) -> dict[str, RuntimeRegistration]:
        registrations = {item.component_id: item for item in self.runtimes}
        if len(registrations) != len(self.runtimes):
            raise ValueError("runtime manifest component IDs must be unique")
        return registrations


def _runtime_manifest(root: Path) -> dict[str, RuntimeRegistration]:
    path = root / ".external-engine-runtimes.json"
    if not path.is_file():
        return {}
    manifest = RuntimeManifest.model_validate_json(path.read_text(encoding="utf-8"))
    if manifest.schema_version != "external-engine-runtime-manifest-v1":
        raise ValueError("unsupported external-engine runtime manifest version")
    return manifest.by_component


def _registered_runtime(root: Path, registration: RuntimeRegistration | None) -> str | None:
    if registration is None:
        return None
    candidate = root.joinpath(registration.path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"registered runtime escapes workspace: {registration.component_id}")
    if not candidate.is_file():
        return None
    hasher = hashlib.sha256()
    with candidate.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    if digest.casefold() != registration.sha256.casefold():
        raise ValueError(f"registered runtime hash mismatch: {registration.component_id}")
    return str(candidate)


def _runtime(
    root: Path,
    names: tuple[str, ...],
    candidates: tuple[str, ...] = (),
    registration: RuntimeRegistration | None = None,
) -> str | None:
    if registration is not None:
        # An explicit manifest entry is authoritative. Missing or invalid
        # registered files never fall back to PATH or legacy candidate paths.
        return _registered_runtime(root, registration)
    for relative in candidates:
        candidate = root.joinpath(relative)
        if candidate.is_file():
            return str(candidate.resolve())
    for name in names:
        found = which(name)
        if found:
            return str(Path(found).resolve())
    return None


def _source(root: Path, relative: str) -> str | None:
    path = root.joinpath(relative)
    return str(path.resolve()) if path.exists() else None


def _verified_receipt_runtime(receipt: Path) -> str | None:
    if not receipt.is_file():
        return None
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    engine = payload.get("engine", {})
    runtime_value = engine.get("runtime_path")
    expected_hash = engine.get("runtime_sha256")
    if not runtime_value or not expected_hash:
        return None
    runtime = Path(runtime_value)
    if not runtime.is_file():
        return None
    hasher = hashlib.sha256()
    with runtime.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    if hasher.hexdigest().casefold() != str(expected_hash).casefold():
        raise ValueError("asset receipt runtime hash mismatch")
    return str(runtime.resolve())


def _engine(
    root: Path, component_id: str, name: str, layer: str,
    executables: tuple[str, ...], source_relative: str | None,
    inputs: tuple[str, ...], outputs: tuple[str, ...],
    *, licensed: bool = False, runtime_candidates: tuple[str, ...] = (),
    runtime_registration: RuntimeRegistration | None = None,
) -> ExternalComponent:
    runtime = _runtime(
        root, executables, runtime_candidates, runtime_registration
    )
    source = _source(root, source_relative) if source_relative else None
    if runtime:
        smoke_receipt = root / ".external-engine-receipts" / f"{component_id}.smoke.json"
        if smoke_receipt.is_file():
            status = ConnectionStatus.READY
            blockers: tuple[str, ...] = ()
        else:
            status = ConnectionStatus.RUNTIME_UNVERIFIED
            blockers = ("Runtime exists, but no successful model smoke-test receipt is registered.",)
    elif licensed:
        status = ConnectionStatus.LICENSE_REQUIRED
        blockers = ("Installed licensed runtime and valid user license are required.",)
    elif source:
        status = ConnectionStatus.SOURCE_ONLY
        blockers = ("Official source is present but no built executable/runtime is available.",)
    else:
        status = ConnectionStatus.RUNTIME_MISSING
        blockers = ("Executable runtime is not installed or discoverable.",)
    return ExternalComponent(
        component_id=component_id, name=name, layer=layer,
        role=FederationRole.LICENSED_ENGINE if licensed else FederationRole.EXECUTION_ENGINE,
        status=status, runtime_path=runtime, source_path=source,
        required_inputs=inputs, declared_outputs=outputs, blockers=blockers,
    )


def _receipted_component(
    root: Path, component_id: str, name: str, layer: str, role: FederationRole,
    inputs: tuple[str, ...], outputs: tuple[str, ...], *,
    source_relative: str | None = None,
    missing_status: ConnectionStatus = ConnectionStatus.RUNTIME_MISSING,
    missing_blocker: str = "A verified local runtime or service client is required.",
) -> ExternalComponent:
    receipt = root / ".external-engine-receipts" / f"{component_id}.smoke.json"
    runtime = _verified_receipt_runtime(receipt)
    source = _source(root, source_relative) if source_relative else None
    if runtime is not None:
        status = ConnectionStatus.READY
        blockers: tuple[str, ...] = ()
    elif source is not None:
        status = ConnectionStatus.SOURCE_ONLY
        blockers = (missing_blocker,)
    else:
        status = missing_status
        blockers = (missing_blocker,)
    return ExternalComponent(
        component_id=component_id, name=name, layer=layer, role=role,
        status=status, runtime_path=runtime, source_path=source,
        required_inputs=inputs, declared_outputs=outputs, blockers=blockers,
    )


def external_federation_inventory(workspace_root: str | Path | None = None) -> FederationInventory:
    root = Path(workspace_root or Path.cwd()).resolve()
    registered = _runtime_manifest(root)
    components = [
        _engine(root,"opensim","OpenSim","musculoskeletal mechanics",("opensim-cmd","opensim"),"vendor/opensim-core",("personal .osim model","motion/controls","external loads"),("muscle force","joint load","mechanical work"),runtime_registration=registered.get("opensim")),
        _engine(root,"moco","OpenSim Moco","musculoskeletal optimal control",(),"vendor/opensim-core",("qualified OpenSim model","task bounds","objective and controls"),("optimized state trajectory","optimized control trajectory","objective value"),runtime_registration=registered.get("moco")),
        _engine(root,"anybody","AnyBody","musculoskeletal cross-check",("AnyBodyCon.exe","AnyBody.exe"),None,("licensed AMMR model","motion"),("muscle recruitment","joint force"),licensed=True,runtime_registration=registered.get("anybody")),
        _engine(root,"febio","FEBio","tissue mechanics",("febio4.exe","febio4","febio.exe","febio"),"vendor/FEBio",("qualified .feb model","OpenSim boundary loads"),("tissue stress","tissue strain"),runtime_candidates=(".scratch/febio/bin/febio4.exe","build/febio/bin/febio4.exe","build/febio/Release/febio4.exe"),runtime_registration=registered.get("febio")),
        _engine(root,"pulse","Pulse","acute whole-body physiology",("PulseScenarioDriver.exe","PulseScenarioDriver"),"vendor/pulse-engine",("patient state","scenario JSON","exercise action"),("cardiovascular trajectory","respiratory trajectory","fluid/renal trajectory"),runtime_candidates=(".scratch/pulse-ascii/install/bin/PulseScenarioDriver.exe","build/pulse/install/bin/PulseScenarioDriver.exe","build/pulse/bin/PulseScenarioDriver.exe"),runtime_registration=registered.get("pulse")),
        _engine(root,"hummod","HumMod","integrated physiology reference",("HumMod.exe",),None,("accepted HumMod terms","HumMod model package"),("integrated physiology trajectory",),licensed=True,runtime_candidates=(".scratch/hummod/HumMod-hummod-standalone-106f109/HumMod.EXE",),runtime_registration=registered.get("hummod")),
        _engine(root,"circadapt","CircAdapt","cardiovascular mechanics/adaptation",("circadapt",),None,("qualified CircAdapt model","cardiac phenotype"),("SV","CO","vascular load"),runtime_candidates=(".scratch/circadapt-venv/Scripts/python.exe",),runtime_registration=registered.get("circadapt")),
        _engine(root,"pk_sim","PK-Sim","substance transport",("PKSim.CLI.exe","PKSim.exe"),None,("qualified PBPK project/snapshot","substance intervention"),("organ concentration trajectory",),runtime_registration=registered.get("pk_sim")),
        _engine(root,"mobi","MoBi","molecular/QSP",("MoBi.exe",),None,("qualified MoBi project","reaction/signalling intervention"),("molecular state trajectory",),runtime_registration=registered.get("mobi")),
        _engine(root,"physicell","PhysiCell","cell/repair",("PhysiCell.exe","PhysiCell"),".scratch/physicell-1.14.2/PhysiCell",("compiled problem-specific PhysiCell model","local environment"),("cell population trajectory",),runtime_candidates=(".scratch/physicell-template-win/project.exe",)),
        _engine(root,"cobra","COBRApy","constraint-based metabolic optimization",(),None,("qualified metabolic model","exchange bounds","objective"),("flux solution","objective value")),
    ]
    components.extend((
        _receipted_component(
            root, "myosuite", "MyoSuite", "neuromuscular motor control",
            FederationRole.EXECUTION_ENGINE,
            ("qualified MyoSuite task", "controls or policy"),
            ("muscle-driven state trajectory", "task reward"),
            missing_blocker="Local inference runtime or remote learning runner is required.",
        ),
        _receipted_component(
            root, "simvascular_lite", "SimVascular svVascularize",
            "vascular geometry and multi-fidelity hemodynamics",
            FederationRole.EXECUTION_ENGINE,
            ("qualified vascular geometry", "boundary conditions"),
            ("vascular geometry", "low-fidelity hemodynamic model inputs"),
            missing_blocker="Local svVascularize runtime is required; 3D CFD/FSI remains remote-only.",
        ),
        _receipted_component(
            root, "libcellml", "libCellML", "CellML model standard and parser",
            FederationRole.ARCHITECTURE_REFERENCE,
            ("CellML 2.0 model asset",), ("validated parsed model", "serialized CellML"),
            missing_blocker="A verified libCellML runtime is required.",
        ),
        _receipted_component(
            root, "sparc", "SPARC Client / Zinc", "neural-organ connectivity data",
            FederationRole.DATA_KNOWLEDGE,
            ("public dataset identifier", "optional user credentials"),
            ("dataset metadata", "anatomical scaffold export"),
            missing_blocker="Public client is absent; restricted services additionally require credentials.",
        ),
        _receipted_component(
            root, "opencap", "OpenCap Core", "video-to-biomechanical state input",
            FederationRole.DATA_KNOWLEDGE,
            ("OpenCap account", "compatible multi-camera capture"),
            ("3D kinematics", "OpenSim-compatible motion"),
            source_relative=".scratch/opencap-core",
            missing_status=ConnectionStatus.SOURCE_ONLY,
            missing_blocker="Official source is installed, but supported processing requires an OpenCap account and capture session.",
        ),
        _engine(
            root, "sim4life", "Sim4Life", "high-fidelity EM thermal neural multiphysics",
            ("Sim4Life.exe",), None,
            ("licensed model", "qualified geometry", "solver protocol"),
            ("EM field", "thermal field", "neural stimulation result"),
            licensed=True,
        ),
    ))
    if find_spec("opensim") is not None:
        for index, component_id in ((0, "opensim"), (1, "moco")):
            item = components[index]
            receipt = root / ".external-engine-receipts" / f"{component_id}.smoke.json"
            components[index] = item.model_copy(update={
                "status": ConnectionStatus.READY if receipt.is_file() else ConnectionStatus.RUNTIME_UNVERIFIED,
                "runtime_path": "python:opensim",
                "blockers": () if receipt.is_file() else (
                    "Python API exists, but no successful component-specific smoke-test receipt is registered.",
                ),
            })
    if find_spec("cobra") is not None:
        index = next(
            index for index, item in enumerate(components)
            if item.component_id == "cobra"
        )
        item = components[index]
        receipt = root / ".external-engine-receipts" / "cobra.smoke.json"
        components[index] = item.model_copy(update={
            "status": ConnectionStatus.READY if receipt.is_file() else ConnectionStatus.RUNTIME_UNVERIFIED,
            "runtime_path": "python:cobra",
            "blockers": () if receipt.is_file() else (
                "Python API exists, but no successful COBRApy solver smoke-test receipt is registered.",
            ),
        })
    human_gem_model = root / "vendor/Human-GEM/model/Human-GEM.xml"
    human_gem_receipt = root / ".external-engine-receipts/human_gem.smoke.json"
    human_gem_ready = human_gem_model.is_file() and human_gem_receipt.is_file()
    components.append(ExternalComponent(
        component_id="human_gem",
        name="Human-GEM",
        layer="genome-scale human metabolism",
        role=FederationRole.MODEL_ASSET,
        status=(
            ConnectionStatus.MODEL_ASSET_READY
            if human_gem_ready else ConnectionStatus.MODEL_ASSET_REQUIRED
        ),
        source_path=(str(human_gem_model.resolve()) if human_gem_model.is_file() else None),
        required_inputs=("exchange bounds", "objective", "biological context"),
        declared_outputs=("constraint-based metabolic flux solution",),
        blockers=() if human_gem_ready else (
            "Pinned Human-GEM SBML asset and successful load/solve receipt are required.",
        ),
    ))
    mitocore_model = root / "vendor/MitoCore/mitocore_v1.01.xml"
    mitocore_receipt = root / ".external-engine-receipts/mitocore.smoke.json"
    mitocore_ready = mitocore_model.is_file() and mitocore_receipt.is_file()
    components.append(ExternalComponent(
        component_id="mitocore",
        name="MitoCore",
        layer="curated constraint-based mitochondrial reference",
        role=FederationRole.MODEL_ASSET,
        status=(
            ConnectionStatus.MODEL_ASSET_READY
            if mitocore_ready else ConnectionStatus.MODEL_ASSET_REQUIRED
        ),
        source_path=(str(mitocore_model.resolve()) if mitocore_model.is_file() else None),
        required_inputs=("exchange bounds", "objective", "biological context"),
        declared_outputs=("mitochondrial metabolic flux reference solution",),
        blockers=() if mitocore_ready else (
            "Pinned MitoCore model asset and successful COBRA solve receipt are required.",
        ),
    ))
    qsp_source = root / "vendor/mitochondria-metabolism"
    qsp_installed = qsp_source.joinpath("Cell_dxdT.m").is_file()
    qsp_receipt = root / ".external-engine-receipts/mitochondria_qsp.smoke.json"
    qsp_runtime = _verified_receipt_runtime(qsp_receipt)
    qsp_ready = qsp_installed and qsp_receipt.is_file() and qsp_runtime is not None
    components.append(ExternalComponent(
        component_id="mitochondria_qsp",
        name="Myocardial Mitochondria Metabolism QSP",
        layer="mechanistic mitochondrial OXPHOS and substrate metabolism",
        role=FederationRole.MODEL_ASSET,
        status=(
            ConnectionStatus.MODEL_ASSET_READY
            if qsp_ready else ConnectionStatus.MODEL_ASSET_REQUIRED
        ),
        runtime_path=qsp_runtime,
        source_path=(str(qsp_source.resolve()) if qsp_installed else None),
        required_inputs=("qualified parameter set", "initial state", "workload protocol"),
        declared_outputs=("OXPHOS fluxes", "metabolite state trajectory", "membrane energetics"),
        blockers=() if qsp_ready else ((
            "Pinned source is installed, but MATLAB 2019b-compatible execution and a successful model smoke receipt are required."
            if qsp_installed else
            "Pinned Pfizer QSP model source, compatible MATLAB runtime, and model smoke receipt are required."
        ),),
    ))
    references = (
        ("harvey_harvetta","Harvey / Harvetta","whole-body metabolism",FederationRole.MODEL_ASSET,ConnectionStatus.MODEL_ASSET_REQUIRED),
        ("vmh","VMH","metabolic knowledge",FederationRole.DATA_KNOWLEDGE,ConnectionStatus.REFERENCE_ONLY),
        ("uiss","UISS","immune simulation",FederationRole.MODEL_ASSET,ConnectionStatus.MODEL_ASSET_REQUIRED),
        ("o2s2parc","o2S2PARC","co-simulation reference",FederationRole.ORCHESTRATION_REFERENCE,ConnectionStatus.REFERENCE_ONLY),
        ("edith_vht","EDITH / EU VHT","federation architecture",FederationRole.ARCHITECTURE_REFERENCE,ConnectionStatus.REFERENCE_ONLY),
    )
    components.extend(ExternalComponent(
        component_id=cid,name=name,layer=layer,role=role,status=status,
        blockers=(("A qualified executable model asset and compatible solver adapter are required." if status is ConnectionStatus.MODEL_ASSET_REQUIRED else "This component supplies data, standards, or architecture; it is not an execution engine."),),
    ) for cid,name,layer,role,status in references)
    executable = tuple(item.component_id for item in components if item.role in {FederationRole.EXECUTION_ENGINE,FederationRole.LICENSED_ENGINE})
    blocking = tuple(item.component_id for item in components if item.component_id in executable and item.status is not ConnectionStatus.READY)
    return FederationInventory(components=tuple(components),executable_component_ids=executable,ready_for_execution=not blocking,blocking_component_ids=blocking)


class ExternalFederationNotReadyError(RuntimeError):
    pass


def require_external_federation_ready(workspace_root: str | Path | None = None) -> FederationInventory:
    inventory = external_federation_inventory(workspace_root)
    if not inventory.ready_for_execution:
        raise ExternalFederationNotReadyError(
            "external federation is not executable; blocked components="
            + ",".join(inventory.blocking_component_ids)
        )
    return inventory


__all__ = ["ConnectionStatus","ExternalComponent","ExternalFederationNotReadyError","FederationInventory","FederationRole","external_federation_inventory","require_external_federation_ready"]
