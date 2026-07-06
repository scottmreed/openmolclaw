"""Local model provider (OpenMolClaw harness).

Talks to a local, chat-completions-compatible endpoint — the kind
exposed by common local runtimes on ``http://localhost:11434/v1`` and similar.
No API key is required by default; set one only if your local gateway asks for
it.

This is a public-safe :class:`~..interfaces.ModelProvider`. It names no vendor:
you point it at an endpoint and a model id (e.g. an OLMo-style local model).

Standard-library + ``requests``.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from ..interfaces import Message, ToolSpec
from .base import BaseChatCompletionsProvider


class LocalProvider(BaseChatCompletionsProvider):
    """chat-completions-compatible provider for a locally hosted model.

    Example config (``docs/model_providers.md``)::

        model:
          provider: local
          model: olmo
          endpoint: http://localhost:11434/v1
    """

    def __init__(
        self,
        model: str,
        endpoint: str = "http://localhost:11434/v1",
        api_key: Optional[str] = None,
        timeout: float = 120.0,
    ) -> None:
        super().__init__(model=model, base_url=endpoint)
        self.api_key = api_key
        self.timeout = timeout

    def complete_with_tools(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        tool_choice: Any = None,
    ) -> Dict[str, Any]:
        import requests  # local import keeps import-time deps minimal

        body = self.build_request(messages, tools, tool_choice)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            json=body,
            headers=headers,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()


__all__ = ["LocalProvider"]
