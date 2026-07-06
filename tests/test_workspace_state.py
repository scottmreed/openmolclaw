"""Workspace state + alias + serialization round-trip tests."""
from openmolclaw.workspace import aliases
from openmolclaw.workspace.serialization import dumps, from_snapshot, loads, to_snapshot
from openmolclaw.workspace.state import WorkspaceState


def test_alias_allocation_monotonic():
    existing = ["[m1]", "[m2]", "[r1]"]
    assert aliases.next_alias("molecule", existing) == "[m3]"
    assert aliases.next_alias("reaction", existing) == "[r2]"
    assert aliases.next_alias("label", existing) == "[label1]"


def test_add_get_remove():
    state = WorkspaceState.new("t")
    m1 = state.add("molecule", {"smiles": "CCO"})
    assert m1 == "[m1]"
    assert state.get(m1)["smiles"] == "CCO"
    assert state.list_aliases("molecule") == ["[m1]"]
    state.remove(m1)
    assert len(state) == 0


def test_serialization_round_trip():
    state = WorkspaceState.new("t")
    state.add("molecule", {"smiles": "CCO"})
    state.add("reaction", {"rxn": "CCO>>CC=O"})
    restored = loads(dumps(state.workspace))
    assert restored.objects == state.workspace.objects
    assert from_snapshot(to_snapshot(restored)).workspace_id == "t"


def test_local_json_store_round_trip(tmp_path):
    from openmolclaw.harness.defaults import LocalJSONWorkspaceStore

    store = LocalJSONWorkspaceStore(root=tmp_path)
    state = WorkspaceState.new("persist")
    state.add("molecule", {"smiles": "c1ccccc1"})
    state.save(store)
    reloaded = WorkspaceState.load(store, "persist")
    assert reloaded.get("[m1]")["smiles"] == "c1ccccc1"
