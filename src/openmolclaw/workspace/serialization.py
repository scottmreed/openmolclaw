"""Workspace serialization (OpenMolClaw workspace).

Stable JSON snapshot format for a :class:`~..harness.interfaces.Workspace`. The
snapshot is versioned so future format changes stay backward-compatible, and it
round-trips losslessly: ``from_snapshot(to_snapshot(ws)) == ws``.

Standard-library only.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from ..harness.interfaces import Workspace

SNAPSHOT_VERSION = 1


def to_snapshot(workspace: Workspace) -> Dict[str, Any]:
    """Serialize a workspace to a plain, JSON-safe dict."""
    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "workspace_id": workspace.workspace_id,
        "objects": workspace.objects,
        "metadata": workspace.metadata,
    }


def from_snapshot(data: Dict[str, Any]) -> Workspace:
    """Rebuild a workspace from a snapshot dict.

    Tolerant of the pre-version shape (no ``snapshot_version`` key).
    """
    version = data.get("snapshot_version", SNAPSHOT_VERSION)
    if version > SNAPSHOT_VERSION:
        raise ValueError(
            f"snapshot version {version} is newer than supported {SNAPSHOT_VERSION}"
        )
    return Workspace(
        workspace_id=data.get("workspace_id", "local"),
        objects=dict(data.get("objects", {})),
        metadata=dict(data.get("metadata", {})),
    )


def dumps(workspace: Workspace, *, indent: int = 2) -> str:
    return json.dumps(to_snapshot(workspace), indent=indent, sort_keys=True)


def loads(text: str) -> Workspace:
    return from_snapshot(json.loads(text))


__all__ = ["SNAPSHOT_VERSION", "to_snapshot", "from_snapshot", "dumps", "loads"]
