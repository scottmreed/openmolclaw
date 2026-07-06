"""/api/chat route contracts (Flask test client, scripted provider — no network)."""

from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest

from openmolclaw.app import create_app
from openmolclaw.harness.defaults import LocalJSONWorkspaceStore


class FakeProvider:
    def __init__(self, responses):
        self._responses: List[Any] = list(responses)

    def complete_with_tools(self, messages, tools, tool_choice=None):
        r = self._responses.pop(0) if self._responses else ""
        if isinstance(r, dict):
            r = json.dumps(r)
        return {"choices": [{"message": {"content": r}}]}


class RaisingProvider:
    def complete_with_tools(self, messages, tools, tool_choice=None):
        raise RuntimeError("endpoint unreachable")


def _decision(tool_name: str, **args) -> Dict[str, Any]:
    return {
        "intent": "action" if tool_name else "question",
        "tool_name": tool_name,
        "tool_args": args,
        "conversational": not tool_name,
        "confidence": 0.9,
    }


STOP = _decision("")


def _client(tmp_path, provider_factory=None, config=None):
    store = LocalJSONWorkspaceStore(root=tmp_path / "ws")
    app = create_app(store=store, provider_factory=provider_factory, config=config)
    app.testing = True
    return app.test_client()


def test_chat_runs_tool_and_returns_structure(tmp_path):
    factory = lambda cfg: FakeProvider(  # noqa: E731
        [_decision("render_molecule", smiles="CCO"), STOP, "Here's ethanol rendered."]
    )
    client = _client(tmp_path, provider_factory=factory)
    r = client.post("/api/chat", json={"message": "draw CCO", "history": []})
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["reply"] == "Here's ethanol rendered."
    assert any(s["tool_name"] == "render_molecule" for s in body["steps"])
    assert body["workspace"] and "<svg" in body["workspace"][0]["svg"]
    # The rendered structure was persisted to the workspace.
    ws = client.get("/api/workspace").get_json()
    assert body["workspace"][0]["alias"] in ws["objects"]


def test_chat_requires_message(tmp_path):
    factory = lambda cfg: FakeProvider([STOP, "hi"])  # noqa: E731
    client = _client(tmp_path, provider_factory=factory)
    r = client.post("/api/chat", json={"message": "   "})
    assert r.status_code == 400
    assert r.get_json()["error_type"] == "bad_arguments"


def test_chat_provider_unavailable_is_soft_error(tmp_path):
    factory = lambda cfg: RaisingProvider()  # noqa: E731
    client = _client(tmp_path, provider_factory=factory)
    r = client.post("/api/chat", json={"message": "hello"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is False
    assert body["error_type"] == "provider_unavailable"
    assert body["reply"]  # user-facing message present


def test_chat_provider_not_configured(tmp_path):
    # No factory + an exotic provider name with no endpoint → UnknownProvider.
    client = _client(tmp_path, config={"model": {"provider": "mystery"}})
    r = client.post("/api/chat", json={"message": "hello"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is False
    assert body["error_type"] == "provider_not_configured"


def test_chat_private_structure_mode_blocks_lookup(tmp_path):
    # Router picks lookup_compound; the host gate denies it under PSM, and the
    # turn still returns a reply explaining the block.
    factory = lambda cfg: FakeProvider(  # noqa: E731
        [_decision("lookup_compound", name="aspirin"), "External lookups are disabled."]
    )
    config = {"model": {"provider": "local", "privacy": {"private_structure_mode": True}}}
    client = _client(tmp_path, provider_factory=factory, config=config)
    r = client.post("/api/chat", json={"message": "look up aspirin"})
    body = r.get_json()
    assert body["ok"] is True
    step = next(s for s in body["steps"] if s["tool_name"] == "lookup_compound")
    assert step["ok"] is False and step["error_type"] == "gate_denied"


def test_chat_routes_to_deferred_rdkit_agent_tool(tmp_path):
    factory = lambda cfg: FakeProvider(  # noqa: E731
        [
            _decision(
                "rdkit_agent_similarity_search",
                query_smiles="CCO",
                target_smiles=["CCN"],
            ),
            STOP,
            "I prepared a deferred rdkit-agent similarity search. OpenMolClaw did not run the CLI.",
        ]
    )
    client = _client(tmp_path, provider_factory=factory)
    r = client.post("/api/chat", json={"message": "compare CCO to CCN", "history": []})
    body = r.get_json()
    assert body["ok"] is True
    step = next(s for s in body["steps"] if s["tool_name"] == "rdkit_agent_similarity_search")
    assert step["ok"] is True
    assert step["result"]["execution_status"] == "deferred_external_tool"
    assert "did not run the CLI" in body["reply"]
    # Deferred payloads are not molecules — no workspace object should be created.
    assert body["workspace"] == []
