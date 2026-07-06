"""No hidden fallback under ZDR Mode (PRD §14.3)."""

from __future__ import annotations

import pytest
import requests

from openmolclaw.harness.providers.openrouter import OpenRouterProvider


class _ErrorResponse:
    status_code = 429

    def raise_for_status(self):
        raise requests.HTTPError("429 Too Many Requests")

    def json(self):  # pragma: no cover - not reached
        return {}


def test_allow_fallbacks_false_present_when_zdr_on():
    provider = OpenRouterProvider(
        model="allenai/olmo-2-0325-32b-instruct", api_key="k", openrouter_zdr=True
    )
    policy = provider.provider_policy()
    assert policy["zdr"] is True
    assert policy["allow_fallbacks"] is False


def test_http_error_raises_without_retrying_another_endpoint(monkeypatch):
    calls = {"n": 0}

    def fake_post(*a, **k):
        calls["n"] += 1
        return _ErrorResponse()

    monkeypatch.setattr(requests, "post", fake_post)
    provider = OpenRouterProvider(
        model="allenai/olmo-2-0325-32b-instruct", api_key="k", openrouter_zdr=True
    )
    with pytest.raises(requests.HTTPError):
        provider.complete_with_tools(messages=[{"role": "user", "content": "hi"}], tools=[])
    # Exactly one request — no silent retry through a second provider/endpoint.
    assert calls["n"] == 1


def test_provider_policy_empty_only_when_all_controls_off():
    provider = OpenRouterProvider(
        model="m",
        api_key="k",
        openrouter_zdr=False,
        deny_data_collection=False,
        require_parameters=False,
    )
    assert provider.provider_policy() == {}
