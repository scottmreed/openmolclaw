"""OpenRouter-compatible model provider (OpenMolClaw harness).

Talks to an OpenRouter-compatible chat-completions endpoint. OpenRouter exposes
many models behind one chat-completions API; OpenMolClaw treats it as a
configured endpoint + model id and never silently switches providers.

The API key is read from the ``OPENROUTER_API_KEY`` environment variable by
default (never hard-coded, never committed).

Fail-closed policy
------------------
The provider refuses to run rather than degrade silently:

* No API key → :class:`RuntimeError` (never a silent no-auth call, never a
  fallback to another provider).
* When tool support is required (the default) and a **preflight** check finds
  the configured model has *no active endpoint* or *no endpoint advertising
  tool-calling*, it raises :class:`ProviderEndpointError` before spending a
  request. The preflight's decision logic (:func:`evaluate_openrouter_model`)
  is a pure function so it is unit-testable with no network. The live network
  preflight is opt-in (``preflight=True`` or ``OPENMOLCLAW_PROVIDER_PREFLIGHT=1``)
  so local contract tests never require connectivity.

Standard-library + ``requests``.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Sequence

from ..interfaces import Message, ToolSpec
from .base import BaseChatCompletionsProvider

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


class ProviderEndpointError(RuntimeError):
    """Raised when a selected model has no usable / tool-capable endpoint."""


class ZDRUnavailableError(ProviderEndpointError):
    """Raised (fail-closed) when ZDR routing is required but cannot be verified.

    Distinct subclass so callers can tell "no tool support" apart from "no ZDR
    endpoint" and surface the right feature-loss message.
    """


def evaluate_zdr_endpoint(
    model: str,
    zdr_records: Sequence[Dict[str, Any]],
) -> Optional[bool]:
    """Decide whether ``model`` is served by a Zero Data Retention endpoint.

    ``zdr_records`` is the payload from OpenRouter's ``GET /endpoints/zdr``
    (shape may evolve). Pure — no network — so it is unit-testable with canned
    data. Tolerant of shape:

    * Returns ``True``  — a ZDR record clearly matches ``model``.
    * Returns ``False`` — records exist and carry model ids, but none match.
    * Returns ``None``  — the payload provides no model ids to check against, so
      ZDR support is *unverifiable* from this endpoint and the caller decides
      (warn vs. fail) based on its fail-closed policy.
    """
    saw_any_id = False
    for rec in zdr_records or []:
        if not isinstance(rec, dict):
            continue
        candidates = [
            rec.get("id"),
            rec.get("model"),
            rec.get("canonical_slug"),
            rec.get("slug"),
        ]
        # Some shapes nest the id under a "model" object or list "models".
        model_obj = rec.get("model")
        if isinstance(model_obj, dict):
            candidates += [model_obj.get("id"), model_obj.get("slug")]
        for m in rec.get("models") or []:
            saw_any_id = True
            if m == model:
                return True
        for c in candidates:
            if isinstance(c, str):
                saw_any_id = True
                if c == model:
                    return True
    return False if saw_any_id else None


def evaluate_openrouter_model(
    model: str,
    model_records: Sequence[Dict[str, Any]],
    *,
    require_tools: bool = True,
) -> bool:
    """Fail-closed check that ``model`` is usable on OpenRouter.

    ``model_records`` is the ``data`` list from OpenRouter's ``GET /models``
    (each record may carry ``id`` / ``canonical_slug``, a ``supported_parameters``
    list, and optionally an ``endpoints`` list). Pure — no network — so it can be
    unit-tested with canned records.

    Raises :class:`ProviderEndpointError` if the model is absent, has an explicit
    empty endpoint list, or (when ``require_tools``) advertises no tool-calling
    support anywhere. Returns ``True`` when the model is usable.
    """
    rec = next(
        (
            m
            for m in model_records
            if m.get("id") == model or m.get("canonical_slug") == model
        ),
        None,
    )
    if rec is None:
        raise ProviderEndpointError(
            f"OpenRouter has no model matching {model!r}; nothing to route to "
            f"(fail-closed, no fallback)."
        )

    endpoints = rec.get("endpoints")
    if endpoints is not None and len(endpoints) == 0:
        raise ProviderEndpointError(
            f"OpenRouter model {model!r} has no active endpoint (fail-closed)."
        )

    if require_tools:
        params = set(rec.get("supported_parameters") or [])
        for endpoint in endpoints or []:
            params |= set(endpoint.get("supported_parameters") or [])
        if "tools" not in params:
            raise ProviderEndpointError(
                f"OpenRouter model {model!r} advertises no tool-calling support "
                f"('tools' not in supported_parameters); the router-first harness "
                f"requires tools, so this fails closed rather than silently "
                f"dropping tool calls."
            )
    return True


class OpenRouterProvider(BaseChatCompletionsProvider):
    """chat-completions-compatible provider for an OpenRouter endpoint.

    Example config (``docs/model_providers.md``)::

        model:
          provider: openrouter
          model: google/gemma-4-26b-a4b-it
          base_url: https://openrouter.ai/api/v1
    """

    def __init__(
        self,
        model: str,
        base_url: str = DEFAULT_BASE_URL,
        api_key: Optional[str] = None,
        timeout: float = 120.0,
        referer: Optional[str] = None,
        title: str = "OpenMolClaw",
        require_tool_support: bool = True,
        use_zdr: bool = False,
        preflight: Optional[bool] = None,
        openrouter_zdr: Optional[bool] = None,
        deny_data_collection: bool = True,
        allow_fallbacks: bool = False,
        require_parameters: bool = True,
        fail_closed_zdr_preflight: bool = True,
    ) -> None:
        super().__init__(model=model, base_url=base_url)
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self.timeout = timeout
        self.referer = referer
        self.title = title
        self.require_tool_support = require_tool_support
        # ``use_zdr`` is the legacy flag; ``openrouter_zdr`` supersedes it when
        # given. Keep ``use_zdr`` as a live alias so old callers keep working.
        self.openrouter_zdr = bool(use_zdr) if openrouter_zdr is None else bool(openrouter_zdr)
        self.use_zdr = self.openrouter_zdr
        self.deny_data_collection = bool(deny_data_collection)
        self.allow_fallbacks = bool(allow_fallbacks)
        self.require_parameters = bool(require_parameters)
        self.fail_closed_zdr_preflight = bool(fail_closed_zdr_preflight)
        # Live preflight is opt-in: explicit arg wins, else the env flag.
        self.preflight_enabled = (
            preflight
            if preflight is not None
            else _env_truthy("OPENMOLCLAW_PROVIDER_PREFLIGHT")
        )
        # ZDR endpoint preflight (GET /endpoints/zdr) is a separate opt-in so
        # offline/dev stays simple; it only runs when ZDR routing is required.
        self.zdr_preflight_enabled = _env_truthy("OPENMOLCLAW_OPENROUTER_ZDR_PREFLIGHT")

    def provider_policy(self) -> Dict[str, Any]:
        """Build the OpenRouter ``provider`` routing object for this request.

        Empty dict means "attach nothing". When any privacy control is active,
        ``allow_fallbacks`` is always emitted so a privacy-sensitive request can
        never inherit OpenRouter's default-on provider fallbacks.
        """
        policy: Dict[str, Any] = {}
        if self.openrouter_zdr:
            policy["zdr"] = True
        if self.deny_data_collection:
            policy["data_collection"] = "deny"
        if self.openrouter_zdr or self.deny_data_collection or self.require_parameters:
            policy["allow_fallbacks"] = bool(self.allow_fallbacks)
        if self.require_parameters:
            policy["require_parameters"] = True
        return policy

    def fetch_zdr_endpoints(self) -> list:
        """Fetch OpenRouter's ZDR endpoint catalog (network). Opt-in only."""
        import requests

        resp = requests.get(
            f"{self.base_url}/endpoints/zdr",
            headers=self._headers(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", data if isinstance(data, list) else [])

    def zdr_preflight(self) -> Optional[bool]:
        """Verify the configured model is a ZDR endpoint (fail-closed).

        Returns the :func:`evaluate_zdr_endpoint` verdict. Raises
        :class:`ZDRUnavailableError` when the model is known-absent, or (when it
        is merely unverifiable) only if ``fail_closed_zdr_preflight`` is set.
        """
        verdict = evaluate_zdr_endpoint(self.model, self.fetch_zdr_endpoints())
        if verdict is True:
            return True
        if verdict is False:
            raise ZDRUnavailableError(
                f"OpenRouter reports no Zero Data Retention endpoint for model "
                f"{self.model!r}; ZDR Mode fails closed rather than sending the "
                f"structure to a non-ZDR endpoint."
            )
        # Unverifiable (no model ids in payload).
        if self.fail_closed_zdr_preflight:
            raise ZDRUnavailableError(
                f"Could not verify a Zero Data Retention endpoint for model "
                f"{self.model!r} from OpenRouter's ZDR catalog; failing closed."
            )
        return None

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Title": self.title,
        }
        if self.referer:
            headers["HTTP-Referer"] = self.referer
        return headers

    def fetch_model_records(self) -> list:
        """Fetch OpenRouter's model catalog (network). Used by :meth:`preflight`."""
        import requests

        resp = requests.get(
            f"{self.base_url}/models", headers=self._headers(), timeout=self.timeout
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", data if isinstance(data, list) else [])

    def preflight(self) -> bool:
        """Live fail-closed check that the configured model is usable.

        Fetches the catalog and applies :func:`evaluate_openrouter_model`. Raises
        :class:`ProviderEndpointError` on any problem.
        """
        records = self.fetch_model_records()
        return evaluate_openrouter_model(
            self.model, records, require_tools=self.require_tool_support
        )

    def build_request(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        tool_choice: Any = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        policy = self.provider_policy()
        if policy:
            extra.setdefault("provider", policy)
        return super().build_request(messages, tools, tool_choice, **extra)

    def complete_with_tools(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        tool_choice: Any = None,
    ) -> Dict[str, Any]:
        import requests

        if not self.api_key:
            raise RuntimeError(
                "OpenRouter API key not set. Export OPENROUTER_API_KEY or pass "
                "api_key= to OpenRouterProvider. (Fail-closed: OpenMolClaw does not "
                "fall back to any other provider.)"
            )
        if self.preflight_enabled:
            # Raises ProviderEndpointError if the model can't serve tool calls.
            self.preflight()
        if self.openrouter_zdr and self.zdr_preflight_enabled:
            # Raises ZDRUnavailableError if no ZDR endpoint can be verified.
            self.zdr_preflight()
        body = self.build_request(messages, tools, tool_choice)
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            json=body,
            headers=self._headers(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()


__all__ = [
    "OpenRouterProvider",
    "ProviderEndpointError",
    "ZDRUnavailableError",
    "evaluate_openrouter_model",
    "evaluate_zdr_endpoint",
    "DEFAULT_BASE_URL",
]
