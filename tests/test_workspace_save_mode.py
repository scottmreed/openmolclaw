"""Workspace save-mode: local_json vs memory_only (PRD §14.6)."""

from __future__ import annotations

import pytest

from openmolclaw.app import create_app
from openmolclaw.harness.defaults import InMemoryWorkspaceStore, LocalJSONWorkspaceStore
from openmolclaw.privacy import resolve_workspace_save_mode
from openmolclaw.workspace.state import WorkspaceState


def test_resolve_save_mode_precedence(monkeypatch):
    assert resolve_workspace_save_mode({"save_mode": "memory_only"}) == "memory_only"
    assert resolve_workspace_save_mode({}) == "local_json"
    monkeypatch.setenv("OPENMOLCLAW_WORKSPACE_SAVE_MODE", "memory_only")
    assert resolve_workspace_save_mode({}) == "memory_only"
    # Explicit config value beats env.
    assert resolve_workspace_save_mode({"save_mode": "local_json"}) == "local_json"
    # Unknown values fall back safely.
    assert resolve_workspace_save_mode({"save_mode": "nonsense"}) == "local_json"


def test_local_json_store_writes_file(tmp_path):
    store = LocalJSONWorkspaceStore(root=tmp_path / "ws")
    state = WorkspaceState.new("t")
    state.add("molecule", {"smiles": "CCO"})
    state.save(store)
    assert list((tmp_path / "ws").glob("*.json"))


def test_in_memory_store_writes_no_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = InMemoryWorkspaceStore()
    state = WorkspaceState.new("t")
    alias = state.add("molecule", {"smiles": "CCO"})
    state.save(store)
    # Round-trips through memory…
    assert alias in store.load("t").objects
    # …but nothing is written to disk.
    assert not (tmp_path / ".openmolclaw").exists()


def test_render_memory_only_leaves_no_disk_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = create_app(config={"model": {"provider": "local"}, "workspace": {"save_mode": "memory_only"}})
    app.testing = True
    client = app.test_client()
    r = client.post("/api/render", json={"smiles": "CCO"})
    assert r.status_code == 200
    assert r.get_json()["ok"] is True
    # Memory-only render persisted nothing to .openmolclaw/workspaces.
    assert not (tmp_path / ".openmolclaw").exists()
    # And the privacy endpoint agrees.
    p = client.get("/api/privacy").get_json()
    assert p["workspace_save_mode"] == "memory_only"
    assert p["local_workspace_disk_path"] is None
