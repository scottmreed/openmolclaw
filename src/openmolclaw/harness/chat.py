"""Conversational chat loop (OpenMolClaw harness).

Public-owned. This is the piece that turns the harness's provider-neutral
:class:`~.router.Router` and :class:`~.executor.ToolExecutor` into a real
multi-turn chat turn. A single :func:`run_chat_turn` call:

1. routes the user's message to at most one tool (model call #1),
2. runs that tool through the executor (with gating + tracing),
3. optionally repeats, bounded by ``max_tool_steps``, re-routing with the
   tool observations fed back so the model can chain a couple of steps,
4. asks the model to write the natural-language reply (model call #2 — the
   "responder"), grounded only in what the tools actually returned.

It carries no vendor, plan, quota, or storage coupling — those attach through
the same :class:`~.interfaces.ModelProvider`, :class:`~.interfaces.ToolGate`,
and :class:`~.interfaces.UsageSink` seams the rest of the harness uses. A host
(e.g. the local Flask app) reuses this loop unchanged and layers its own
workspace persistence on top.

Standard-library + Pydantic (via the router/executor envelopes).

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .executor import ToolExecutor, ToolResult
from .interfaces import Message, ModelProvider, ToolGate, UsageEvent, UsageSink
from .router import Router, _extract_text
from .tool_registry import ToolRegistry

logger = logging.getLogger("openmolclaw.harness.chat")

#: The responder writes the user-facing reply. It never selects tools (that is
#: the router's job) and it names no model vendor — the reply's quality is the
#: configured model's, whatever the operator chose.
RESPONDER_SYSTEM_PROMPT = (
    "You are a local chemistry assistant running on the user's own machine. "
    "You help with 2D molecular structures, SMILES, and cheminformatics using "
    "the results of local RDKit tools. Write a concise, accurate reply for the "
    "user in plain language. When a tool returned a structure or numeric "
    "properties, summarize exactly those values — never invent numbers, "
    "structures, or results the tools did not return. If a tool failed, say so "
    "plainly and suggest a next step. Keep chemistry explanations clear and "
    "correct."
)

#: How much of a tool result to surface to the model as an observation. Tool
#: results are small JSON dicts; rendered SVGs can be large, so they are elided
#: from the observation text (the host still gets the full result).
_OBSERVATION_CHAR_BUDGET = 1200


@dataclass
class ChatToolStep:
    """One tool dispatch inside a chat turn, in host-friendly form."""

    tool_name: str
    tool_args: Dict[str, Any]
    ok: bool
    result: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    duration_ms: float = 0.0

    @classmethod
    def from_result(cls, result: ToolResult, tool_args: Dict[str, Any]) -> "ChatToolStep":
        return cls(
            tool_name=result.tool_name,
            tool_args=dict(tool_args or {}),
            ok=result.ok,
            result=result.result,
            error=result.error,
            error_type=result.error_type,
            duration_ms=result.duration_ms,
        )


@dataclass
class ChatTurnResult:
    """Everything a host needs to render one assistant turn."""

    reply: str
    conversational: bool
    intent: str
    steps: List[ChatToolStep] = field(default_factory=list)
    trace: List[Dict[str, Any]] = field(default_factory=list)
    messages: List[Message] = field(default_factory=list)


def _elide(value: Any) -> str:
    """Compact, structure-SVG-free JSON for feeding a result back to the model."""
    try:
        if isinstance(value, dict):
            value = {k: v for k, v in value.items() if k != "svg"}
        text = json.dumps(value, default=str)
    except (TypeError, ValueError):
        text = str(value)
    if len(text) > _OBSERVATION_CHAR_BUDGET:
        text = text[:_OBSERVATION_CHAR_BUDGET] + "…"
    return text


def _observation_message(step: ChatToolStep) -> Message:
    if step.ok:
        content = f"[tool:{step.tool_name} ok] {_elide(step.result)}"
    else:
        content = f"[tool:{step.tool_name} error:{step.error_type}] {step.error}"
    return {"role": "assistant", "content": content}


def _respond(
    provider: ModelProvider,
    history: Sequence[Message],
    user_message: str,
    steps: Sequence[ChatToolStep],
    usage_sink: Optional[UsageSink],
) -> str:
    """Second model call: synthesize the user-facing reply from tool results."""
    messages: List[Message] = [{"role": "system", "content": RESPONDER_SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    for step in steps:
        messages.append(_observation_message(step))

    response = provider.complete_with_tools(messages=messages, tools=[], tool_choice="none")
    if usage_sink is not None:
        usage_sink.record(UsageEvent(kind="model_call", metadata={"stage": "responder"}))
    text = _extract_text(response).strip()
    if text:
        return text
    # Fail-soft: never return an empty bubble. Summarize the tool results
    # deterministically so the user still gets something useful.
    return _fallback_reply(steps)


def _fallback_reply(steps: Sequence[ChatToolStep]) -> str:
    if not steps:
        return "I don't have anything to add yet — try asking about a molecule or a SMILES string."
    lines = []
    for step in steps:
        if step.ok:
            lines.append(f"- {step.tool_name}: {_elide(step.result)}")
        else:
            lines.append(f"- {step.tool_name} failed: {step.error}")
    return "Here is what the tools returned:\n" + "\n".join(lines)


def run_chat_turn(
    user_message: str,
    history: Optional[Sequence[Message]] = None,
    *,
    provider: ModelProvider,
    registry: ToolRegistry,
    executor: Optional[ToolExecutor] = None,
    tool_gate: Optional[ToolGate] = None,
    usage_sink: Optional[UsageSink] = None,
    max_tool_steps: int = 3,
    caller_id: Optional[str] = None,
    surface: str = "chat",
) -> ChatTurnResult:
    """Run one conversational turn: route → execute (bounded) → respond.

    ``history`` is prior provider-neutral messages (``{"role", "content"}``);
    it is not mutated. The returned :class:`ChatTurnResult` includes an updated
    ``messages`` list (history + this user turn + the assistant reply) that a
    stateless host can hand back to the client to carry the conversation.

    The tool loop is bounded and self-terminating: it stops when the router
    returns a conversational decision, when a tool errors, when the router
    repeats a ``(tool, args)`` it already ran this turn, or when
    ``max_tool_steps`` is reached — so a misbehaving model cannot spin.
    """
    history = list(history or [])
    router = Router(provider, usage_sink=usage_sink)
    ex = executor or ToolExecutor(registry, tool_gate=tool_gate, usage_sink=usage_sink)
    tools = registry.specs()

    steps: List[ChatToolStep] = []
    seen: set = set()
    conversational = True
    last_intent = "question"

    for _ in range(max(1, max_tool_steps)):
        router_history = list(history) + [_observation_message(s) for s in steps]
        decision = router.route(user_message, tools, history=router_history)
        last_intent = decision.intent or last_intent
        if decision.conversational or not decision.tool_name:
            break
        signature = (decision.tool_name, json.dumps(decision.tool_args, sort_keys=True, default=str))
        if signature in seen:
            # The model asked for a step it already ran — stop rather than loop.
            break
        seen.add(signature)
        conversational = False
        result = ex.execute(
            decision.tool_name, decision.tool_args, caller_id=caller_id, surface=surface
        )
        steps.append(ChatToolStep.from_result(result, decision.tool_args))
        if not result.ok:
            break

    reply = _respond(provider, history, user_message, steps, usage_sink)
    messages = list(history) + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": reply},
    ]
    return ChatTurnResult(
        reply=reply,
        conversational=conversational,
        intent=last_intent,
        steps=steps,
        trace=list(ex.trace.entries),
        messages=messages,
    )


__all__ = [
    "RESPONDER_SYSTEM_PROMPT",
    "ChatToolStep",
    "ChatTurnResult",
    "run_chat_turn",
]
