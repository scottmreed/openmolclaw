"""Provider policy: explicit choices, fail-closed, no silent OpenAI fallback."""

from __future__ import annotations

import pytest

from openmolclaw.config import (
    UnknownProvider,
    build_provider,
    describe_provider,
)
from openmolclaw.harness.providers.local import LocalProvider
from openmolclaw.harness.providers.openrouter import (
    OpenRouterProvider,
    ProviderEndpointError,
    evaluate_openrouter_model,
)


def test_default_provider_is_local_bundled():
    provider = build_provider()
    assert isinstance(provider, LocalProvider)
    assert describe_provider()["bundled"] is True


@pytest.mark.parametrize("name", ["openai", "claude", "anthropic", "gemini", "custom"])
def test_named_provider_requires_explicit_endpoint(name):
    with pytest.raises(UnknownProvider):
        build_provider({"model": {"provider": name, "model": "x"}})


@pytest.mark.parametrize("name", ["openai", "claude", "anthropic", "gemini", "custom"])
def test_named_provider_with_endpoint_uses_explicit_chat_completions_endpoint(name):
    provider = build_provider(
        {
            "model": {
                "provider": name,
                "model": "chosen-model",
                "endpoint": "https://example.test/v1",
                "api_key": "test-key",
            }
        }
    )
    assert isinstance(provider, LocalProvider)
    assert provider.model == "chosen-model"
    assert provider.base_url == "https://example.test/v1"
    assert describe_provider({"model": {"provider": name, "model": "chosen-model"}})[
        "bundled"
    ] is False


def test_unknown_provider_errors():
    with pytest.raises(UnknownProvider):
        build_provider({"model": {"provider": "make-believe"}})


def test_openrouter_requires_key_fail_closed():
    provider = OpenRouterProvider(model="google/gemma-4-26b-a4b-it", api_key="")
    with pytest.raises(RuntimeError):
        provider.complete_with_tools(messages=[{"role": "user", "content": "hi"}], tools=[])


def test_openrouter_zdr_request_adds_provider_preference():
    # The legacy ``use_zdr`` flag still enables ZDR routing, now with the full
    # privacy-forward provider policy (deny data collection, disable fallbacks,
    # require parameters) rather than a bare ``{"zdr": True}``.
    provider = OpenRouterProvider(
        model="google/gemma-4-26b-a4b-it",
        api_key="test-key",
        use_zdr=True,
    )
    assert provider.openrouter_zdr is True
    body = provider.build_request(
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
    )
    assert body["provider"] == {
        "zdr": True,
        "data_collection": "deny",
        "allow_fallbacks": False,
        "require_parameters": True,
    }


def test_openrouter_absent_model_fails_closed():
    with pytest.raises(ProviderEndpointError):
        evaluate_openrouter_model("vendor/missing", [])


def test_openrouter_no_endpoint_fails_closed():
    records = [{"id": "vendor/model", "endpoints": []}]
    with pytest.raises(ProviderEndpointError):
        evaluate_openrouter_model("vendor/model", records)


def test_openrouter_no_tool_support_fails_closed():
    records = [{"id": "vendor/model", "supported_parameters": ["temperature"]}]
    with pytest.raises(ProviderEndpointError):
        evaluate_openrouter_model("vendor/model", records, require_tools=True)


def test_openrouter_tool_support_ok():
    records = [{"id": "vendor/model", "supported_parameters": ["tools"]}]
    assert evaluate_openrouter_model("vendor/model", records) is True
    # endpoint-level advertisement also counts
    records2 = [{"id": "vendor/model", "endpoints": [{"supported_parameters": ["tools"]}]}]
    assert evaluate_openrouter_model("vendor/model", records2) is True
