"""Stable public facade for the modular research workspace adapter.

The implementation is split by responsibility while this class preserves the
existing Module Interface used by MCP, the JSON CLI, and callers.
"""
from __future__ import annotations

from ._workspace_audit import WorkspaceAuditMixin
from ._workspace_common import DEFAULT_DATABASE
from ._workspace_core import WorkspaceCoreMixin
from ._workspace_evidence import WorkspaceEvidenceMixin
from ._workspace_observations import WorkspaceObservationMixin
from ._workspace_operations import WorkspaceOperationMixin


class FrontierScienceWorkspace(
    WorkspaceOperationMixin,
    WorkspaceAuditMixin,
    WorkspaceObservationMixin,
    WorkspaceEvidenceMixin,
    WorkspaceCoreMixin,
):
    """Persistence and passive model execution without workflow governance."""


__all__ = ["DEFAULT_DATABASE", "FrontierScienceWorkspace"]
