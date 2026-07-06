"""OpenRouter ZDR request-body shape (PRD §14.2).

Monkeypatch ``requests.post`` and assert the request body carries the full ZDR
provider policy and is not stripped by request-kwarg filtering.
"""

from __future__ import annotations

import pytest
import requests

from openmolclaw.harness.providers.base import filter_provider_request_kwargs
from openmolclaw.harness.providers.openrouter import OpenRouterProvider


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _zdr_provider():
    return OpenRouterProvider(
        model="allenai/olmo-2-0325-32b-instruct",
        api_key="test-key",
        openrouter_zdr=True,
    )


def test_request_body_contains_full_zdr_policy(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["body"] = json
        return _FakeResponse({"choices": []})

    monkeypatch.setattr(requests, "post", fake_post)

    provider = _zdr_provider()
    messages = [{"role": "user", "content": "hi"}]
    tools = [{"type": "function", "function": {"name": "noop", "parameters": {}}}]
    provider.complete_with_tools(messages=messages, tools=tools)

    body = captured["body"]
    assert body["provider"] == {
        "zdr": True,
        "data_collection": "deny",
        "allow_fallbacks": False,
        "require_parameters": True,
    }
    # messages and tools are otherwise unchanged.
    assert body["messages"] == messages
    assert body["tools"] == tools
    assert captured["url"].endswith("/chat/completions")


def test_provider_key_survives_request_kwarg_filter():
    # The ``provider`` key must be in the allowed set so it is never dropped.
    policy = {"zdr": True, "data_collection": "deny", "allow_fallbacks": False}
    filtered = filter_provider_request_kwargs({"model": "m", "provider": policy})
    assert filtered["provider"] == policy


def test_missing_api_key_fails_before_any_request(monkeypatch):
    def exploding_post(*a, **k):  # pragma: no cover - must never be called
        raise AssertionError("no request should be made without an API key")

    monkeypatch.setattr(requests, "post", exploding_post)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    provider = OpenRouterProvider(
        model="allenai/olmo-2-0325-32b-instruct", api_key="", openrouter_zdr=True
    )
    with pytest.raises(RuntimeError):
        provider.complete_with_tools(messages=[{"role": "user", "content": "hi"}], tools=[])
