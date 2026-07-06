"""OpenMolClaw — public-safe default adapter implementations.

These are the no-op / local-file defaults the harness ships with. They let the
generic harness run with no external services and no metering — exactly what a
local FOSS user gets out of the box. A host that needs metering, gating, or
durable storage supplies its own implementations of the interfaces in
``interfaces.py``.

Standard-library only.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Union

from .interfaces import (
    GateResult,
    ToolContext,
    UsageEvent,
    Workspace,
)

logger = logging.getLogger("openmolclaw.harness")


class LocalLogUsageSink:
    """Default :class:`~.interfaces.UsageSink`: log usage events, meter nothing.

    The harness has no notion of billing; usage is informational only.
    """

    def record(self, event: UsageEvent) -> None:
        logger.debug(
            "usage kind=%s model=%s tool=%s total_tokens=%s",
            event.kind,
            event.model,
            event.tool_name,
            event.total_tokens,
        )


class AllowAllToolGate:
    """Default :class:`~.interfaces.ToolGate`: allow every tool for every caller.

    The harness imposes no quota or access limits; gating is a host concern.
    """

    def check(self, tool_name: str, context: ToolContext) -> GateResult:  # noqa: ARG002
        return GateResult.allow()


class LocalJSONWorkspaceStore:
    """Default :class:`~.interfaces.WorkspaceStore`: persist workspaces as JSON files.

    Workspaces are written to ``<root>/<workspace_id>.json`` using an atomic
    replace so a crashed write never corrupts an existing workspace. No
    database, no account system.
    """

    def __init__(self, root: Union[str, os.PathLike, None] = None) -> None:
        self.root = (
            Path(root)
            if root is not None
            else Path.cwd() / ".openmolclaw" / "workspaces"
        )

    def _path(self, workspace_id: str) -> Path:
        # Guard against path traversal in workspace ids.
        safe = workspace_id.replace(os.sep, "_")
        if os.altsep:
            safe = safe.replace(os.altsep, "_")
        safe = safe.replace("..", "_")
        return self.root / f"{safe}.json"

    def load(self, workspace_id: str) -> Workspace:
        path = self._path(workspace_id)
        if not path.exists():
            return Workspace(workspace_id=workspace_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        return Workspace(
            workspace_id=data.get("workspace_id", workspace_id),
            objects=data.get("objects", {}),
            metadata=data.get("metadata", {}),
        )

    def save(self, workspace: Workspace) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "workspace_id": workspace.workspace_id,
            "objects": workspace.objects,
            "metadata": workspace.metadata,
        }
        target = self._path(workspace.workspace_id)
        fd, tmp = tempfile.mkstemp(dir=str(self.root), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)


class InMemoryWorkspaceStore:
    """A :class:`~.interfaces.WorkspaceStore` that never writes to disk.

    Workspaces live in this process's memory for the app session only — nothing
    is written under ``.openmolclaw/workspaces``. This backs the "memory-only"
    workspace save mode for cautious users who do not want rendered structures
    persisted to local files. It still retains structures in RAM for the session,
    which is why the honest claim is "not written to disk by OpenMolClaw", not
    "never retained anywhere".
    """

    def __init__(self) -> None:
        self._workspaces: dict = {}

    def load(self, workspace_id: str) -> Workspace:
        existing = self._workspaces.get(workspace_id)
        if existing is None:
            return Workspace(workspace_id=workspace_id)
        # Return a fresh copy so callers mutate their own state, not the store's.
        return Workspace(
            workspace_id=existing.workspace_id,
            objects=dict(existing.objects),
            metadata=dict(existing.metadata),
        )

    def save(self, workspace: Workspace) -> None:
        self._workspaces[workspace.workspace_id] = Workspace(
            workspace_id=workspace.workspace_id,
            objects=dict(workspace.objects),
            metadata=dict(workspace.metadata),
        )


__all__ = [
    "LocalLogUsageSink",
    "AllowAllToolGate",
    "LocalJSONWorkspaceStore",
    "InMemoryWorkspaceStore",
]
