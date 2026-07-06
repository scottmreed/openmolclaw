"""Config parsing for OpenRouter ZDR Mode (PRD §14.1)."""

from __future__ import annotations

import textwrap

import pytest

from openmolclaw.config import build_provider, describe_provider, load_config
from openmolclaw.harness.providers.local import LocalProvider
from openmolclaw.harness.providers.openrouter import OpenRouterProvider


def _write(tmp_path, text: str):
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return p


def test_privacy_block_enables_zdr(tmp_path):
    cfg = load_config(
        _write(
            tmp_path,
            """
            model:
              provider: openrouter
              model: allenai/olmo-2-0325-32b-instruct
              api_key: test-key
              privacy:
                openrouter_zdr: true
                deny_data_collection: true
                allow_fallbacks: false
                require_parameters: true
            """,
        )
    )
    provider = build_provider(cfg)
    assert isinstance(provider, OpenRouterProvider)
    assert provider.openrouter_zdr is True
    assert provider.deny_data_collection is True
    assert provider.allow_fallbacks is False
    assert provider.require_parameters is True


def test_legacy_top_level_zdr_still_enables(tmp_path):
    cfg = load_config(
        _write(
            tmp_path,
            """
            model:
              provider: openrouter
              model: allenai/olmo-2-0325-32b-instruct
              zdr: true
            """,
        )
    )
    provider = build_provider(cfg)
    assert provider.openrouter_zdr is True


def test_env_overrides_default(monkeypatch):
    monkeypatch.setenv("OPENMOLCLAW_OPENROUTER_ZDR", "1")
    cfg = {"model": {"provider": "openrouter", "model": "allenai/olmo-2-0325-32b-instruct"}}
    provider = build_provider(cfg)
    assert provider.openrouter_zdr is True
    # Explicit config value beats the env var.
    cfg2 = {
        "model": {
            "provider": "openrouter",
            "model": "allenai/olmo-2-0325-32b-instruct",
            "privacy": {"openrouter_zdr": False},
        }
    }
    assert build_provider(cfg2).openrouter_zdr is False


def test_describe_provider_reports_privacy_without_secrets():
    cfg = {
        "model": {
            "provider": "openrouter",
            "model": "allenai/olmo-2-0325-32b-instruct",
            "api_key": "super-secret-key",
            "privacy": {"openrouter_zdr": True},
        }
    }
    info = describe_provider(cfg)
    assert info["privacy"]["openrouter_zdr"] is True
    assert info["privacy"]["deny_data_collection"] is True
    assert info["privacy"]["allow_fallbacks"] is False
    assert info["privacy"]["require_parameters"] is True
    # No secret leaks into the descriptive summary.
    import json

    assert "super-secret-key" not in json.dumps(info)


def test_local_provider_ignores_zdr_but_reports_local():
    cfg = {"model": {"provider": "local", "model": "olmo", "zdr": True}}
    provider = build_provider(cfg)
    assert isinstance(provider, LocalProvider)
    assert describe_provider(cfg)["provider"] == "local"


def test_privacy_forward_defaults_without_privacy_block():
    # Even without a privacy block, deny_data_collection + no-fallbacks hold.
    cfg = {"model": {"provider": "openrouter", "model": "allenai/olmo-2-0325-32b-instruct"}}
    provider = build_provider(cfg)
    assert provider.openrouter_zdr is False
    assert provider.deny_data_collection is True
    assert provider.allow_fallbacks is False
    assert provider.require_parameters is True
