"""Provider base helpers (OpenMolClaw harness).

Shared plumbing for the concrete model providers: request-parameter filtering
(so a provider only forwards keyword arguments an endpoint accepts) and a small
base class that both the local and OpenRouter providers extend.

No model vendor is named here — providers are configured by endpoint + model
id, not hard-coded. Standard-library only.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Sequence, Set

# Chat-completion request parameters OpenMolClaw understands and may forward to
# a chat-completions-compatible endpoint. Anything outside this set is dropped so a
# stricter endpoint does not 400 on an unknown field.
KNOWN_REQUEST_PARAMS: Set[str] = {
    "model",
    "messages",
    "tools",
    "tool_choice",
    "temperature",
    "top_p",
    "max_tokens",
    "stop",
    "seed",
    "response_format",
    "stream",
    "provider",
}


def filter_provider_request_kwargs(
    kwargs: Dict[str, Any],
    *,
    allowed: Optional[Iterable[str]] = None,
    drop: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Return a copy of ``kwargs`` limited to known/allowed request params.

    ``allowed`` overrides the default known set; ``drop`` removes specific keys
    an endpoint is known not to support (e.g. a model that rejects
    ``temperature``). ``None`` values are always removed.
    """
    allow: Set[str] = set(allowed) if allowed is not None else set(KNOWN_REQUEST_PARAMS)
    dropset: Set[str] = set(drop or ())
    out: Dict[str, Any] = {}
    for k, v in kwargs.items():
        if k in dropset or v is None:
            continue
        if k in allow:
            out[k] = v
    return out


class BaseChatCompletionsProvider:
    """Common request shaping for chat-completions-compatible chat endpoints.

    Concrete subclasses set ``base_url`` and provide credentials/transport.
    The base only builds the request body and applies parameter filtering; it
    never names a vendor.
    """

    #: Params a specific configured model is known not to accept.
    unsupported_params: Set[str] = set()

    def __init__(self, model: str, base_url: str) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

    def build_request(
        self,
        messages: Sequence[Dict[str, Any]],
        tools: Sequence[Dict[str, Any]],
        tool_choice: Any = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
        }
        if tools:
            body["tools"] = list(tools)
            if tool_choice is not None:
                body["tool_choice"] = tool_choice
        body.update(extra)
        return filter_provider_request_kwargs(body, drop=self.unsupported_params)


__all__ = [
    "KNOWN_REQUEST_PARAMS",
    "filter_provider_request_kwargs",
    "BaseChatCompletionsProvider",
]
