"""Workspace state (OpenMolClaw workspace).

A small, in-memory workspace that holds molecules / reactions / labels keyed by
their semantic aliases (see ``aliases.py``). It wraps the provider-neutral
:class:`~..harness.interfaces.Workspace` value type and can be persisted through
any :class:`~..harness.interfaces.WorkspaceStore` (the public default writes
local JSON).

Standard-library only.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..harness.interfaces import Workspace, WorkspaceStore
from . import aliases


class WorkspaceState:
    """Mutable view over a :class:`Workspace` with alias allocation."""

    def __init__(self, workspace: Optional[Workspace] = None) -> None:
        self.workspace = workspace or Workspace(workspace_id="local")

    # --- construction -----------------------------------------------------
    @classmethod
    def new(cls, workspace_id: str = "local") -> "WorkspaceState":
        return cls(Workspace(workspace_id=workspace_id))

    @classmethod
    def load(cls, store: WorkspaceStore, workspace_id: str) -> "WorkspaceState":
        return cls(store.load(workspace_id))

    def save(self, store: WorkspaceStore) -> None:
        store.save(self.workspace)

    # --- objects ----------------------------------------------------------
    @property
    def objects(self) -> Dict[str, Any]:
        return self.workspace.objects

    def add(self, object_type: str, payload: Dict[str, Any]) -> str:
        """Add an object of ``object_type`` and return its new alias."""
        alias = aliases.next_alias(object_type, self.workspace.objects.keys())
        record = {"type": object_type, **payload}
        self.workspace.objects[alias] = record
        return alias

    def get(self, alias: str) -> Dict[str, Any]:
        try:
            return self.workspace.objects[alias]
        except KeyError:
            raise KeyError(f"no object at alias {alias!r}")

    def update(self, alias: str, payload: Dict[str, Any]) -> None:
        obj = self.get(alias)
        obj.update(payload)

    def remove(self, alias: str) -> None:
        self.workspace.objects.pop(alias, None)

    def list_aliases(self, object_type: Optional[str] = None) -> List[str]:
        keys = list(self.workspace.objects.keys())
        if object_type is None:
            return keys
        prefix = aliases.prefix_for_type(object_type)
        out = []
        for k in keys:
            try:
                p, _ = aliases.parse_alias(k)
            except ValueError:
                continue
            if p == prefix:
                out.append(k)
        return out

    def __len__(self) -> int:
        return len(self.workspace.objects)


__all__ = ["WorkspaceState"]
