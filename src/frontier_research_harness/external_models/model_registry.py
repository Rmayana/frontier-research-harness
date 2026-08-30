"""Unified external scientific-model registry contracts.

This is the canonical projection target for runtime discovery, model assets,
and knowledge sources.  Discovery remains delegated to the existing external
federation so this layer does not invent installation state.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path

from pydantic import Field, model_validator

from frontier_research_harness.scientific_contracts import NonEmptyStr, ScientificModel

from .external_engine_federation import (
    ConnectionStatus,
    FederationRole,
    external_federation_inventory,
)

class ModelRuntimeStatus(StrEnum):
    READY = "READY"
    RUNTIME_UNVERIFIED = "RUNTIME_UNVERIFIED"
    SOURCE_ONLY = "SOURCE_ONLY"
    INSTALL_REQUIRED = "INSTALL_REQUIRED"
    MODEL_ASSET = "MODEL_ASSET"
    MODEL_ASSET_READY = "MODEL_ASSET_READY"
    DATA_SOURCE = "DATA_SOURCE"
    LICENSE_REQUIRED = "LICENSE_REQUIRED"
    OPTIONAL = "OPTIONAL"
    LEGACY_REFERENCE = "LEGACY_REFERENCE"
    UNAVAILABLE = "UNAVAILABLE"


class ModelRole(StrEnum):
    CORE = "CORE"
    SPECIALIZED = "SPECIALIZED"
    ON_DEMAND = "ON_DEMAND"
    VALIDATION_REFERENCE = "VALIDATION_REFERENCE"
    MODEL_ASSET = "MODEL_ASSET"
    DATA_SOURCE = "DATA_SOURCE"
    ARCHITECTURE_REFERENCE = "ARCHITECTURE_REFERENCE"


class ComputationalCost(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class UnifiedModelRecord(ScientificModel):
    model_id: NonEmptyStr
    name: NonEmptyStr
    version: NonEmptyStr
    domain: NonEmptyStr
    role: ModelRole
    capabilities: tuple[NonEmptyStr, ...]
    requires: tuple[NonEmptyStr, ...]
    produces: tuple[NonEmptyStr, ...]
    runtime_status: ModelRuntimeStatus
    runtime_path: str | None = None
    source_path: str | None = None
    smoke_receipt_path: str | None = None
    asset_receipt_path: str | None = None
    computational_cost: ComputationalCost = ComputationalCost.UNKNOWN
    expected_latency_seconds: float | None = Field(default=None, ge=0)
    fidelity: NonEmptyStr = "model-specific"
    scale: NonEmptyStr = "model-specific"
    temporal_resolution: NonEmptyStr = "model-specific"
    context_of_use: tuple[NonEmptyStr, ...] = ()
    validation_status: NonEmptyStr = "unqualified for personal prediction"
    uncertainty_support: NonEmptyStr = "adapter-specific"
    adapter_id: str | None = None
    license: NonEmptyStr = "upstream terms apply"
    blockers: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def runtime_evidence_matches_status(self) -> "UnifiedModelRecord":
        if self.runtime_status is ModelRuntimeStatus.READY:
            if not self.runtime_path or not self.smoke_receipt_path:
                raise ValueError("READY model requires runtime and smoke receipt")
        if self.smoke_receipt_path is not None and self.runtime_status is not ModelRuntimeStatus.READY:
            raise ValueError("only READY models may expose a smoke receipt")
        if self.runtime_status is ModelRuntimeStatus.MODEL_ASSET_READY:
            if not self.source_path or not self.asset_receipt_path:
                raise ValueError("MODEL_ASSET_READY requires source and asset receipt")
        if self.asset_receipt_path is not None and self.runtime_status is not ModelRuntimeStatus.MODEL_ASSET_READY:
            raise ValueError("only MODEL_ASSET_READY records may expose an asset receipt")
        return self


class UnifiedModelRegistry(ScientificModel):
    registry_id: NonEmptyStr = "human-digital-twin-model-registry-v1"
    records: tuple[UnifiedModelRecord, ...]

    @model_validator(mode="after")
    def model_ids_are_unique(self) -> "UnifiedModelRegistry":
        ids = [record.model_id for record in self.records]
        if len(ids) != len(set(ids)):
            raise ValueError("unified model registry IDs must be unique")
        return self

    def get(self, model_id: str) -> UnifiedModelRecord:
        match = next((record for record in self.records if record.model_id == model_id), None)
        if match is None:
            raise KeyError(model_id)
        return match

    def ready_models(self) -> tuple[UnifiedModelRecord, ...]:
        return tuple(
            record for record in self.records
            if record.runtime_status is ModelRuntimeStatus.READY
        )


_STATUS_MAP = {
    ConnectionStatus.READY: ModelRuntimeStatus.READY,
    ConnectionStatus.RUNTIME_UNVERIFIED: ModelRuntimeStatus.RUNTIME_UNVERIFIED,
    ConnectionStatus.SOURCE_ONLY: ModelRuntimeStatus.SOURCE_ONLY,
    ConnectionStatus.RUNTIME_MISSING: ModelRuntimeStatus.INSTALL_REQUIRED,
    ConnectionStatus.LICENSE_REQUIRED: ModelRuntimeStatus.LICENSE_REQUIRED,
    ConnectionStatus.MODEL_ASSET_REQUIRED: ModelRuntimeStatus.MODEL_ASSET,
    ConnectionStatus.MODEL_ASSET_READY: ModelRuntimeStatus.MODEL_ASSET_READY,
    ConnectionStatus.REFERENCE_ONLY: ModelRuntimeStatus.DATA_SOURCE,
}


def _model_role(component_id: str, federation_role: FederationRole) -> ModelRole:
    if component_id == "hummod":
        return ModelRole.VALIDATION_REFERENCE
    if component_id in {"pulse", "febio", "circadapt", "opensim", "moco", "pk_sim", "mobi", "cobra"}:
        return ModelRole.CORE
    if component_id in {"physicell", "anybody", "myosuite", "simvascular_lite", "sim4life"}:
        return ModelRole.ON_DEMAND
    if federation_role is FederationRole.MODEL_ASSET:
        return ModelRole.MODEL_ASSET
    if federation_role is FederationRole.DATA_KNOWLEDGE:
        return ModelRole.DATA_SOURCE
    if federation_role in {
        FederationRole.ORCHESTRATION_REFERENCE,
        FederationRole.ARCHITECTURE_REFERENCE,
    }:
        return ModelRole.ARCHITECTURE_REFERENCE
    return ModelRole.SPECIALIZED


def _receipt_version(root: Path, component_id: str) -> tuple[str, str | None]:
    receipt = root / ".external-engine-receipts" / f"{component_id}.smoke.json"
    if not receipt.is_file():
        installation = root / ".external-engine-receipts" / f"{component_id}.install.json"
        if not installation.is_file():
            return "unverified", None
        payload = json.loads(installation.read_text(encoding="utf-8"))
        return str(
            payload.get("model", {}).get("version")
            or payload.get("engine", {}).get("version", "unknown")
        ), None
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    version = str(
        payload.get("model", {}).get("version")
        or payload.get("engine", {}).get("version", "unknown")
    )
    return version, str(receipt.resolve())


def unified_model_registry(workspace_root: str | Path | None = None) -> UnifiedModelRegistry:
    root = Path(workspace_root or Path.cwd()).resolve()
    federation = external_federation_inventory(root)
    records: list[UnifiedModelRecord] = []
    for component in federation.components:
        version, receipt_path = _receipt_version(root, component.component_id)
        status = _STATUS_MAP[component.status]
        records.append(UnifiedModelRecord(
            model_id=component.component_id,
            name=component.name,
            version=version,
            domain=component.layer,
            role=_model_role(component.component_id, component.role),
            capabilities=component.declared_outputs,
            requires=component.required_inputs,
            produces=component.declared_outputs,
            runtime_status=status,
            runtime_path=component.runtime_path,
            source_path=component.source_path,
            smoke_receipt_path=receipt_path if status is ModelRuntimeStatus.READY else None,
            asset_receipt_path=(
                receipt_path if status is ModelRuntimeStatus.MODEL_ASSET_READY else None
            ),
            adapter_id=(
                "passive.human_gem"
                if component.component_id == "human_gem" and status is ModelRuntimeStatus.MODEL_ASSET_READY
                else "passive.mitocore"
                if component.component_id == "mitocore" and status is ModelRuntimeStatus.MODEL_ASSET_READY
                else "passive.mitochondria_qsp"
                if component.component_id == "mitochondria_qsp" and status is ModelRuntimeStatus.MODEL_ASSET_READY
                else (f"external.{component.component_id}" if component.runtime_path else None)
            ),
            license=("user license required" if component.role is FederationRole.LICENSED_ENGINE else "upstream terms apply"),
            blockers=component.blockers,
        ))
    return UnifiedModelRegistry(records=tuple(records))


__all__ = [name for name in globals() if not name.startswith("_")]
