"""Router-first orchestration (OpenMolClaw harness).

The router is the first of the harness's two model calls. It classifies the
user's request and, when a tool is warranted, selects one tool and prepares its
arguments — returning a structured :class:`~.schemas.RouterDecision`. The
:class:`~.executor.ToolExecutor` then runs the chosen tool.

This is the *provider-neutral* loop: it drives any
:class:`~.interfaces.ModelProvider` and carries no plan/quota/vendor logic. A
host may wrap it with its own provider selection behind the same interface.

Standard-library only (Pydantic for the decision envelope).

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Sequence

from .interfaces import Message, ModelProvider, ToolSpec, UsageEvent, UsageSink
from .schemas import RouterDecision

logger = logging.getLogger("openmolclaw.harness.router")


def parse_router_json_content(content: str) -> Dict[str, Any]:
    """Parse router JSON output from a model.

    Some models emit two identical JSON objects on separate lines; ``json.loads``
    then fails with 'Extra data' — take the first object only. Others wrap the
    JSON in a fenced ```json block, which we strip first.
    """
    text = (content or "").strip()
    if text.startswith("```"):
        # Strip a leading fence line (```json / ```) and a trailing fence.
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        if "Extra data" in str(e) or getattr(e, "msg", None) == "Extra data":
            try:
                obj, _ = json.JSONDecoder().raw_decode(text)
                if isinstance(obj, dict):
                    logger.warning(
                        "Router returned multiple JSON values; using the first object only"
                    )
                    return obj
            except json.JSONDecodeError:
                pass
        raise


ROUTER_SYSTEM_PROMPT = (
    "You are the routing step of a local chemistry agent. Read the user's "
    "message and the list of available tools. Respond with ONLY a JSON object "
    "of the form:\n"
    '{"intent": "action|question|trivial|undo", "tool_name": "<one tool or '
    'empty>", "tool_args": {..}, "conversational": <bool>, "confidence": '
    "<0..1>}\n"
    "Pick at most one tool. If no tool is needed, set tool_name to \"\" and "
    "conversational to true. Never include prose outside the JSON object."
)


class Router:
    """Two-step router: one model call to decide, structured decision out.

    The router asks a :class:`~.interfaces.ModelProvider` to choose a tool given
    the registry's tool specs, parses the JSON reply, and returns a validated
    :class:`~.schemas.RouterDecision`. Robust to models that emit fenced or
    duplicated JSON; falls back to a conversational decision on parse failure.
    """

    def __init__(
        self,
        provider: ModelProvider,
        usage_sink: Optional[UsageSink] = None,
        system_prompt: str = ROUTER_SYSTEM_PROMPT,
    ) -> None:
        self.provider = provider
        self.usage_sink = usage_sink
        self.system_prompt = system_prompt

    def route(
        self,
        user_message: str,
        tools: Sequence[ToolSpec],
        history: Optional[Sequence[Message]] = None,
    ) -> RouterDecision:
        messages: List[Message] = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        response = self.provider.complete_with_tools(
            messages=messages, tools=list(tools), tool_choice="none"
        )
        content = _extract_text(response)
        if self.usage_sink is not None:
            self.usage_sink.record(
                UsageEvent(kind="model_call", metadata={"stage": "router"})
            )

        try:
            data = parse_router_json_content(content)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Router JSON parse failed; treating as conversational")
            return RouterDecision(
                intent="question",
                tool_name="",
                conversational=True,
                confidence=0.0,
            )
        return self.decision_from_payload(data)

    @staticmethod
    def decision_from_payload(data: Dict[str, Any]) -> RouterDecision:
        """Build a :class:`RouterDecision` from a parsed router payload.

        Tolerant of missing keys so partial model output still yields a usable
        decision.
        """
        tool_name = (data.get("tool_name") or "").strip()
        return RouterDecision(
            intent=str(data.get("intent") or ("action" if tool_name else "question")),
            tool_name=tool_name,
            tool_args=dict(data.get("tool_args") or {}),
            conversational=bool(data.get("conversational", not tool_name)),
            confidence=float(data.get("confidence") or 0.0),
        )


def _extract_text(response: Any) -> str:
    """Best-effort extraction of assistant text from a provider response.

    Accepts a plain string, a ``{"content": ...}`` mapping, or an
    chat-completions-compatible ``{"choices": [{"message": {"content": ...}}]}`` shape.
    """
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        if "content" in response and isinstance(response["content"], str):
            return response["content"]
        choices = response.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message") or {}
            return msg.get("content") or ""
    return str(response)


__all__ = ["parse_router_json_content", "Router", "ROUTER_SYSTEM_PROMPT"]
