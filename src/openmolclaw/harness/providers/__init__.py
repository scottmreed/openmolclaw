"""Public model providers for the OpenMolClaw harness.

Two chat-completions-compatible providers ship by default — a local endpoint and an
OpenRouter-compatible endpoint. Neither names a proprietary vendor; both are
configured by endpoint + model id (e.g. an OLMo-style model).
"""

from __future__ import annotations

from .base import BaseChatCompletionsProvider, filter_provider_request_kwargs
from .local import LocalProvider
from .openrouter import OpenRouterProvider

__all__ = [
    "BaseChatCompletionsProvider",
    "filter_provider_request_kwargs",
    "LocalProvider",
    "OpenRouterProvider",
]
