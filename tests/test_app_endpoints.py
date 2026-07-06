"""Flask app-factory endpoint contracts (Flask test client, no network)."""

from __future__ import annotations

import pytest

from openmolclaw.app import create_app
from openmolclaw.harness.defaults import LocalJSONWorkspaceStore


@pytest.fixture()
def client(tmp_path):
    store = LocalJSONWorkspaceStore(root=tmp_path / "ws")
    app = create_app(store=store)
    app.testing = True
    return app.test_client()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["version"]
    assert body["provider"]["provider"] == "local"
    assert set(body["tools"]) >= {"validate_smiles", "render_molecule"}


def test_remote_token_guards_api_requests(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENMOLCLAW_REMOTE_TOKEN", "test-token")
    store = LocalJSONWorkspaceStore(root=tmp_path / "ws")
    app = create_app(store=store)
    app.testing = True
    client = app.test_client()

    missing = client.get("/api/health")
    assert missing.status_code == 401
    assert missing.get_json() == {"ok": False, "error": "remote token required"}

    wrong = client.get("/api/health", headers={"X-OpenMolClaw-Token": "wrong"})
    assert wrong.status_code == 401

    bearer = client.get("/api/health", headers={"Authorization": "Bearer test-token"})
    assert bearer.status_code == 200
    assert bearer.get_json()["ok"] is True

    header = client.get("/api/health", headers={"X-OpenMolClaw-Token": "test-token"})
    assert header.status_code == 200
    assert header.get_json()["ok"] is True


def test_model_options_endpoint_exposes_zdr_options(client):
    r = client.get("/api/model-options")
    assert r.status_code == 200
    body = r.get_json()
    assert body["recommended"] == "openrouter_zdr"
    assert any(
        option["model"] == "google/gemma-4-26b-a4b-it"
        and option["provider"] == "openrouter"
        and option["zdr"] is True
        for option in body["options"]
    )


def test_select_model_updates_runtime_config(client):
    r = client.post(
        "/api/model-options",
        json={"provider": "openrouter", "model": "google/gemma-4-26b-a4b-it", "zdr": True},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["provider"]["provider"] == "openrouter"
    assert body["provider"]["model"] == "google/gemma-4-26b-a4b-it"


def test_list_tools(client):
    body = client.get("/api/tools").get_json()
    names = {s["function"]["name"] for s in body["tools"]}
    assert names == {
        "validate_smiles",
        "render_molecule",
        "convert_smiles",
        "lookup_compound",
        "molecular_descriptors",
        "canonicalize_smiles",
        "to_inchi",
        "substructure_search",
        "functional_groups",
        "stereochemistry",
        "rdkit_agent_similarity_search",
        "rdkit_agent_atom_map",
        "rdkit_agent_reaction_balance_check",
        "rdkit_agent_fingerprint",
    }


def test_execute_ok(client):
    r = client.post("/api/execute", json={"tool": "validate_smiles", "args": {"smiles": "CCO"}})
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["result"]["valid"] is True


def test_execute_unknown_tool_envelope(client):
    r = client.post("/api/execute", json={"tool": "does_not_exist", "args": {}})
    assert r.status_code == 404
    body = r.get_json()
    assert body["ok"] is False
    assert body["error_type"] == "unknown_tool"


def test_named_tool_bad_arguments_envelope(client):
    # validate_smiles requires 'smiles'; omitting it is a bad-arguments envelope.
    r = client.post("/api/tools/validate_smiles", json={})
    assert r.status_code == 400
    assert r.get_json()["error_type"] == "bad_arguments"


def test_render_and_workspace(client):
    r = client.post("/api/render", json={"smiles": "CCO"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] and "<svg" in body["svg"]
    ws = client.get("/api/workspace").get_json()
    assert body["alias"] in ws["objects"]


def test_contracts_route(client):
    r = client.get("/api/contracts")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_docs_json_and_html(client):
    j = client.get("/api/docs").get_json()
    assert "routes" in j and "tools" in j and "ChemIllusion" in j["attribution"]
    html = client.get("/docs")
    assert html.status_code == 200
    assert b"OpenMolClaw" in html.data


def test_execute_each_deferred_rdkit_agent_tool(client):
    cases = [
        (
            "rdkit_agent_similarity_search",
            {"query_smiles": "CCO", "target_smiles": ["CCN"]},
        ),
        ("rdkit_agent_atom_map", {"operation": "check", "smirks": "[CH3:1]>>[CH3:1]"}),
        (
            "rdkit_agent_reaction_balance_check",
            {"reaction_smiles": "CCO>>CC=O"},
        ),
        ("rdkit_agent_fingerprint", {"smiles": ["CCO"]}),
    ]
    for tool, args in cases:
        r = client.post("/api/execute", json={"tool": tool, "args": args})
        assert r.status_code == 200, tool
        body = r.get_json()
        assert body["ok"] is True, tool
        assert body["result"]["execution_status"] == "deferred_external_tool", tool
        assert body["result"]["openmolclaw_executed_cli"] is False, tool


def test_deferred_rdkit_agent_tools_can_be_disabled_via_config(tmp_path):
    from openmolclaw.app import create_app
    from openmolclaw.harness.defaults import LocalJSONWorkspaceStore

    store = LocalJSONWorkspaceStore(root=tmp_path / "ws")
    app = create_app(store=store, config={"tools": {"rdkit_agent_deferred": False}})
    app.testing = True
    disabled_client = app.test_client()
    names = {s["function"]["name"] for s in disabled_client.get("/api/tools").get_json()["tools"]}
    assert "rdkit_agent_similarity_search" not in names
    r = disabled_client.post(
        "/api/execute", json={"tool": "rdkit_agent_similarity_search", "args": {}}
    )
    assert r.get_json()["error_type"] == "unknown_tool"


def test_index_html_includes_rdkit_agent_workflow_form(client):
    r = client.get("/")
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert 'id="rdkit-agent-form"' in html
    assert 'id="rdkit-agent-workflow"' in html
    assert 'id="rdkit-agent-input"' in html
    assert "rdkit-agent" in html  # link text / repo reference present
