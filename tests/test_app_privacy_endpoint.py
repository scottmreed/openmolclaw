"""Flask privacy endpoints (PRD §14.5)."""

from __future__ import annotations

import json

import pytest

from openmolclaw.app import create_app
from openmolclaw.harness.defaults import LocalJSONWorkspaceStore


def _client(config=None, store=None):
    app = create_app(store=store, config=config)
    app.testing = True
    return app.test_client()


ZDR_CONFIG = {
    "model": {
        "provider": "openrouter",
        "model": "allenai/olmo-2-0325-32b-instruct",
        "api_key": "super-secret-key",
        "privacy": {"openrouter_zdr": True},
    }
}


def test_privacy_endpoint_reports_posture(tmp_path):
    client = _client(config=ZDR_CONFIG, store=LocalJSONWorkspaceStore(root=tmp_path / "ws"))
    p = client.get("/api/privacy").get_json()
    assert p["provider"] == "openrouter"
    assert p["openrouter_zdr"] is True
    assert p["deny_data_collection"] is True
    assert p["allow_fallbacks"] is False
    assert p["require_parameters"] is True
    assert p["chemillusion_server_storage"] is False
    assert p["provider_policy"] == {
        "zdr": True,
        "data_collection": "deny",
        "allow_fallbacks": False,
        "require_parameters": True,
    }
    assert p["warnings"]


def test_health_and_docs_never_reveal_api_key(tmp_path):
    client = _client(config=ZDR_CONFIG, store=LocalJSONWorkspaceStore(root=tmp_path / "ws"))
    health = client.get("/api/health").get_json()
    assert "super-secret-key" not in json.dumps(health)
    assert health["privacy"]["openrouter_zdr"] is True

    docs = client.get("/api/docs").get_json()
    assert "super-secret-key" not in json.dumps(docs)
    assert docs["privacy"]["provider"] == "openrouter"

    privacy = client.get("/api/privacy").get_json()
    assert "super-secret-key" not in json.dumps(privacy)


def test_memory_only_reports_disk_persistence_disabled():
    cfg = dict(ZDR_CONFIG)
    cfg = {**ZDR_CONFIG, "workspace": {"save_mode": "memory_only"}}
    client = _client(config=cfg)
    p = client.get("/api/privacy").get_json()
    assert p["workspace_save_mode"] == "memory_only"
    assert p["local_workspace_disk_path"] is None


def test_session_endpoint_toggles_zdr_and_save_mode(tmp_path):
    client = _client(
        config={"model": {"provider": "openrouter", "model": "allenai/olmo-2-0325-32b-instruct"}},
        store=LocalJSONWorkspaceStore(root=tmp_path / "ws"),
    )
    # Turn ZDR on and switch to memory-only for the session.
    r = client.post(
        "/api/privacy/session",
        json={"openrouter_zdr": True, "workspace_save_mode": "memory_only"},
    )
    body = r.get_json()
    assert body["ok"] is True
    assert body["openrouter_zdr"] is True
    assert body["workspace_save_mode"] == "memory_only"
    # Persisted for subsequent reads.
    assert client.get("/api/privacy").get_json()["openrouter_zdr"] is True


def test_local_provider_privacy_posture_is_not_applicable():
    client = _client(config={"model": {"provider": "local", "model": "olmo"}})
    p = client.get("/api/privacy").get_json()
    assert p["provider"] == "local"
    assert p["provider_policy"] == {}
    assert p["openrouter_zdr"] is False


def test_private_structure_mode_off_by_default():
    client = _client(config={"model": {"provider": "local", "model": "olmo"}})
    p = client.get("/api/privacy").get_json()
    assert p["private_structure_mode"] is False
    assert p["blocks_external_lookup"] is False
    assert p["private_structure_mode_claim"] is None


def test_private_structure_mode_local_provider_earns_the_claim(tmp_path):
    client = _client(
        config={"model": {"provider": "local", "model": "olmo"}},
        store=LocalJSONWorkspaceStore(root=tmp_path / "ws"),
    )
    r = client.post("/api/privacy/session", json={"private_structure_mode": True})
    body = r.get_json()
    assert body["private_structure_mode"] is True
    assert body["blocks_external_lookup"] is True
    # Enabling it forces memory-only workspace even though the store started
    # as LocalJSONWorkspaceStore.
    assert body["workspace_save_mode"] == "memory_only"
    assert body["private_structure_mode_claim"] is not None
    assert "Private Structure Mode" in body["private_structure_mode_claim"]

    lookup = client.post("/api/tools/lookup_compound", json={"name": "aspirin"})
    assert lookup.status_code == 403
    assert lookup.get_json()["error_type"] == "gate_denied"


def test_private_structure_mode_forces_zdr_on_openrouter():
    client = _client(
        config={
            "model": {
                "provider": "openrouter",
                "model": "allenai/olmo-2-0325-32b-instruct",
                "api_key": "super-secret-key",
                "privacy": {"private_structure_mode": True},
            }
        }
    )
    p = client.get("/api/privacy").get_json()
    assert p["openrouter_zdr"] is True
    assert p["deny_data_collection"] is True
    assert p["allow_fallbacks"] is False
    assert p["private_structure_mode_claim"] is not None


def test_private_structure_mode_withholds_claim_for_custom_endpoint():
    client = _client(
        config={
            "model": {
                "provider": "my-endpoint",
                "model": "x",
                "endpoint": "https://example.invalid",
                "privacy": {"private_structure_mode": True},
            }
        }
    )
    p = client.get("/api/privacy").get_json()
    assert p["private_structure_mode"] is True
    assert p["blocks_external_lookup"] is True
    assert p["private_structure_mode_claim"] is None
    assert any("custom endpoint" in w for w in p["warnings"])


def test_private_structure_mode_cannot_be_silently_weakened(tmp_path):
    client = _client(
        config={"model": {"provider": "local", "model": "olmo"}},
        store=LocalJSONWorkspaceStore(root=tmp_path / "ws"),
    )
    client.post("/api/privacy/session", json={"private_structure_mode": True})
    r = client.post("/api/privacy/session", json={"workspace_save_mode": "local_json"})
    assert r.get_json()["workspace_save_mode"] == "memory_only"
