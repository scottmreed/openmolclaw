"""Configuration loading + provider policy (OpenMolClaw).

Loads a model-provider configuration from a YAML/JSON file (or a dict) and
builds the matching :class:`~.harness.interfaces.ModelProvider`.

Provider policy (fail-closed, no silent fallback)
-------------------------------------------------
Provider selection is **always an explicit configuration choice**. There is no
implicit default to any commercial vendor and, in particular, *nothing ever
silently falls back to OpenAI*.

* ``local`` and ``openrouter`` are bundled.
* Any provider name is allowed when the user supplies an explicit
  chat-completions-compatible ``endpoint`` or ``base_url``. The name is kept for
  display/config clarity; the request goes only to that endpoint.
* Any provider name without an endpoint is an error. The built-in *default*
  config uses ``local`` so install checks need no secrets.

Config shape::

    model:
      provider: openrouter            # or: local
      model: google/gemma-4-26b-a4b-it
      base_url: https://openrouter.ai/api/v1   # openrouter
      endpoint: http://localhost:11434/v1      # local

Standard-library + PyYAML.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .harness.providers.local import LocalProvider
from .harness.providers.openrouter import OpenRouterProvider
from .privacy import coerce_bool

DEFAULT_CONFIG: Dict[str, Any] = {
    "model": {
        "provider": "local",
        "model": "olmo",
        "endpoint": "http://localhost:11434/v1",
    }
}

OPENROUTER_ZDR_MODEL_OPTIONS = [
    {
        "label": "Gemma 4 26B A4B (ZDR, tools)",
        "provider": "openrouter",
        "model": "google/gemma-4-26b-a4b-it",
        "zdr": True,
        "tool_capable": True,
    },
    {
        "label": "Amazon Nova Lite (ZDR, tools)",
        "provider": "openrouter",
        "model": "amazon/nova-lite-v1",
        "zdr": True,
        "tool_capable": True,
    },
    {
        "label": "DeepSeek V3.2 Exp (ZDR, tools)",
        "provider": "openrouter",
        "model": "deepseek/deepseek-v3.2-exp",
        "zdr": True,
        "tool_capable": True,
    },
    {
        "label": "Qwen3 32B (ZDR, tools)",
        "provider": "openrouter",
        "model": "qwen/qwen3-32b",
        "zdr": True,
        "tool_capable": True,
    },
    {
        "label": "Llama 3.3 70B Instruct (ZDR, tools)",
        "provider": "openrouter",
        "model": "meta-llama/llama-3.3-70b-instruct",
        "zdr": True,
        "tool_capable": True,
    },
    {
        "label": "Claude Sonnet 4.5 via OpenRouter ZDR (tools)",
        "provider": "openrouter",
        "model": "anthropic/claude-sonnet-4.5",
        "zdr": True,
        "tool_capable": True,
    },
    {
        "label": "GPT OSS 20B via OpenRouter ZDR (tools)",
        "provider": "openrouter",
        "model": "openai/gpt-oss-20b",
        "zdr": True,
        "tool_capable": True,
    },
]

#: Providers with a working implementation shipped in the open package.
BUNDLED_PROVIDERS = ("local", "openrouter")

class ProviderConfigError(ValueError):
    """Base class for provider-selection configuration errors."""


class UnknownProvider(ProviderConfigError):
    """Raised when the configured provider name is not recognized at all."""


def load_config(path: Union[str, os.PathLike, None] = None) -> Dict[str, Any]:
    """Load config from a YAML/JSON file, or return the built-in default.

    If ``path`` is ``None`` the loader also checks the ``OPENMOLCLAW_CONFIG``
    environment variable before falling back to :data:`DEFAULT_CONFIG`.
    """
    if path is None:
        env = os.environ.get("OPENMOLCLAW_CONFIG")
        path = env if env else None
    if path is None:
        return dict(DEFAULT_CONFIG)
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix in (".yaml", ".yml"):
        import yaml

        return yaml.safe_load(text) or {}
    return json.loads(text)


def _model_section(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return dict((config or DEFAULT_CONFIG).get("model", {}) or {})


def resolve_privacy_flags(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve the OpenRouter ZDR privacy flags for a ``model`` config section.

    ``cfg`` is a ``_model_section(...)`` dict. Reads the nested ``privacy`` block
    with ``config value > env var > default`` precedence (see
    :func:`openmolclaw.privacy.coerce_bool`). A legacy top-level ``zdr: true`` is
    honored as the default for ``openrouter_zdr`` so older configs keep working.

    Privacy-forward defaults (PRD §9.2): provider data collection is denied and
    provider fallbacks are disabled by default; explicit ZDR routing is opt-in.
    """
    privacy = dict(cfg.get("privacy") or {})
    legacy_zdr = bool(cfg.get("zdr", False))
    return {
        "openrouter_zdr": coerce_bool(
            privacy.get("openrouter_zdr"),
            env="OPENMOLCLAW_OPENROUTER_ZDR",
            default=legacy_zdr,
        ),
        "deny_data_collection": coerce_bool(
            privacy.get("deny_data_collection"),
            env="OPENMOLCLAW_OPENROUTER_DENY_DATA_COLLECTION",
            default=True,
        ),
        "allow_fallbacks": coerce_bool(
            privacy.get("allow_fallbacks"),
            env="OPENMOLCLAW_OPENROUTER_ALLOW_FALLBACKS",
            default=False,
        ),
        "require_parameters": coerce_bool(
            privacy.get("require_parameters"),
            env="OPENMOLCLAW_OPENROUTER_REQUIRE_PARAMETERS",
            default=True,
        ),
        "fail_closed_zdr_preflight": coerce_bool(
            privacy.get("fail_closed_zdr_preflight"),
            env="OPENMOLCLAW_OPENROUTER_ZDR_FAIL_CLOSED",
            default=True,
        ),
        # Private Structure Mode: the combined ZDR + no-external-lookup +
        # no-disk-persistence posture (see openmolclaw.privacy). Off by
        # default; enabling it never silently weakens the other flags above —
        # describe_privacy() forces them on for this provider when it's set.
        "private_structure_mode": coerce_bool(
            privacy.get("private_structure_mode"),
            env="OPENMOLCLAW_PRIVATE_STRUCTURE_MODE",
            default=False,
        ),
    }


def build_provider(config: Optional[Dict[str, Any]] = None):
    """Construct a :class:`ModelProvider` from a loaded config dict.

    Fail-closed: ``local`` and ``openrouter`` have named helpers. Any other
    provider name must include an explicit chat-completions-compatible endpoint.
    Never falls back to another provider.
    """
    cfg = _model_section(config)
    provider = (cfg.get("provider") or "local").strip().lower()
    model = cfg.get("model") or "olmo"

    if provider == "openrouter":
        flags = resolve_privacy_flags(cfg)
        return OpenRouterProvider(
            model=model,
            base_url=cfg.get("base_url") or "https://openrouter.ai/api/v1",
            api_key=cfg.get("api_key"),
            require_tool_support=bool(cfg.get("require_tool_support", True)),
            preflight=cfg.get("preflight"),
            openrouter_zdr=flags["openrouter_zdr"],
            deny_data_collection=flags["deny_data_collection"],
            allow_fallbacks=flags["allow_fallbacks"],
            require_parameters=flags["require_parameters"],
            fail_closed_zdr_preflight=flags["fail_closed_zdr_preflight"],
        )
    if provider == "local":
        return LocalProvider(
            model=model,
            endpoint=cfg.get("endpoint") or "http://localhost:11434/v1",
            api_key=cfg.get("api_key"),
        )
    explicit_endpoint = cfg.get("endpoint") or cfg.get("base_url")
    if explicit_endpoint:
        api_key = cfg.get("api_key")
        api_key_env = cfg.get("api_key_env")
        if not api_key and api_key_env:
            api_key = os.environ.get(str(api_key_env))
        return LocalProvider(
            model=model,
            endpoint=explicit_endpoint,
            api_key=api_key,
        )
    raise UnknownProvider(
        f"provider {provider!r} needs an explicit chat-completions-compatible "
        f"endpoint/base_url; OpenMolClaw never guesses a vendor endpoint or "
        f"falls back to another provider."
    )


def describe_provider(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Summarize the configured provider *without* constructing or calling it.

    Safe for ``/api/health`` and ``doctor``: it never touches the network and
    never raises on an unbundled/unknown provider — it just reports the facts,
    including whether the selection is bundled.
    """
    cfg = _model_section(config)
    provider = (cfg.get("provider") or "local").strip().lower()
    flags = resolve_privacy_flags(cfg)
    return {
        "provider": provider,
        "model": cfg.get("model") or ("olmo" if provider in BUNDLED_PROVIDERS else None),
        "bundled": provider in BUNDLED_PROVIDERS,
        "endpoint": cfg.get("endpoint"),
        "base_url": cfg.get("base_url"),
        # Legacy top-level flag kept for backward compatibility.
        "zdr": flags["openrouter_zdr"],
        # Full resolved posture (no secrets). Only meaningful for openrouter.
        "privacy": {
            "openrouter_zdr": flags["openrouter_zdr"],
            "deny_data_collection": flags["deny_data_collection"],
            "allow_fallbacks": flags["allow_fallbacks"],
            "require_parameters": flags["require_parameters"],
            "private_structure_mode": flags["private_structure_mode"],
        },
    }


__all__ = [
    "DEFAULT_CONFIG",
    "OPENROUTER_ZDR_MODEL_OPTIONS",
    "BUNDLED_PROVIDERS",
    "ProviderConfigError",
    "UnknownProvider",
    "load_config",
    "build_provider",
    "describe_provider",
    "resolve_privacy_flags",
]
