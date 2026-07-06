"""ZDR endpoint preflight decision logic — pure, no network (PRD §14.4)."""

from __future__ import annotations

import pytest
import requests

from openmolclaw.harness.providers.openrouter import (
    OpenRouterProvider,
    ZDRUnavailableError,
    evaluate_zdr_endpoint,
)

MODEL = "allenai/olmo-2-0325-32b-instruct"


def test_model_present_as_zdr_endpoint_passes():
    records = [{"id": MODEL}, {"id": "other/model"}]
    assert evaluate_zdr_endpoint(MODEL, records) is True


def test_model_present_nested_models_list_passes():
    records = [{"provider": "x", "models": [MODEL, "y/z"]}]
    assert evaluate_zdr_endpoint(MODEL, records) is True


def test_model_absent_with_ids_is_false():
    records = [{"id": "a/b"}, {"id": "c/d"}]
    assert evaluate_zdr_endpoint(MODEL, records) is False


def test_unverifiable_payload_is_none():
    # Records carry no model ids at all → unverifiable.
    records = [{"note": "no ids here"}, {"policy": "zdr"}]
    assert evaluate_zdr_endpoint(MODEL, records) is None


def test_zdr_preflight_fails_closed_when_absent(monkeypatch):
    provider = OpenRouterProvider(model=MODEL, api_key="k", openrouter_zdr=True)
    monkeypatch.setattr(provider, "fetch_zdr_endpoints", lambda: [{"id": "a/b"}])
    with pytest.raises(ZDRUnavailableError):
        provider.zdr_preflight()


def test_zdr_preflight_unverifiable_respects_fail_closed_flag(monkeypatch):
    provider = OpenRouterProvider(
        model=MODEL, api_key="k", openrouter_zdr=True, fail_closed_zdr_preflight=False
    )
    monkeypatch.setattr(provider, "fetch_zdr_endpoints", lambda: [{"note": "no ids"}])
    # Unverifiable + not fail-closed → returns None rather than raising.
    assert provider.zdr_preflight() is None


def test_complete_runs_zdr_preflight_when_enabled(monkeypatch):
    monkeypatch.setenv("OPENMOLCLAW_OPENROUTER_ZDR_PREFLIGHT", "1")
    provider = OpenRouterProvider(model=MODEL, api_key="k", openrouter_zdr=True)

    def exploding_post(*a, **k):  # pragma: no cover - must not be reached
        raise AssertionError("request should not be sent when ZDR preflight fails")

    monkeypatch.setattr(requests, "post", exploding_post)
    monkeypatch.setattr(provider, "fetch_zdr_endpoints", lambda: [{"id": "a/b"}])
    with pytest.raises(ZDRUnavailableError):
        provider.complete_with_tools(messages=[{"role": "user", "content": "hi"}], tools=[])
