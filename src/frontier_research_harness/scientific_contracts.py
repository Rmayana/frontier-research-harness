"""Small immutable contracts shared by the active scientific adapters.

This module keeps external-model execution independent from the legacy Harness
Kernel.  It contains validation primitives only; it owns no research workflow.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, JsonValue, StringConstraints


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


def _uuid_text(value: str) -> str:
    parsed = UUID(value)
    if str(parsed) != value:
        raise ValueError("identifier must be a canonical lowercase UUID string")
    return value


UuidText = Annotated[str, AfterValidator(_uuid_text)]


class ScientificModel(BaseModel):
    """Strict JSON contract for model inputs, outputs, and registry records."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _canonical_default(value: Any) -> JsonValue:
    if isinstance(value, datetime):
        if value.utcoffset() != timedelta(0):
            raise ValueError("canonical datetime must be UTC")
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    raise TypeError(f"unsupported canonical JSON value: {type(value)!r}")


def canonical_json_bytes(value: BaseModel | dict[str, Any] | JsonValue) -> bytes:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=_canonical_default,
    ).encode("utf-8")


def canonical_sha256(value: BaseModel | dict[str, Any] | JsonValue) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
