"""Chat loop contracts (offline, scripted fake provider — no network)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence

import pytest

from openmolclaw.builtin_tools import build_default_registry
from openmolclaw.harness.chat import run_chat_turn


class FakeProvider:
    """Returns queued responses in order; records each call.

    A ``dict`` is passed through as-is (a router decision is JSON *text*, so
    wrap it in a chat-completions shape); a ``str`` becomes assistant content.
    """

    def __init__(self, responses: Sequence[Any]):
        self._responses: List[Any] = list(responses)
        self.calls: List[Dict[str, Any]] = []

    def complete_with_tools(self, messages, tools, tool_choice=None):
        self.calls.append(
            {"messages": list(messages), "tools": list(tools), "tool_choice": tool_choice}
        )
        r = self._responses.pop(0) if self._responses else ""
        if isinstance(r, dict):
            r = json.dumps(r)
        return {"choices": [{"message": {"content": r}}]}


def _decision(tool_name: str, **args) -> Dict[str, Any]:
    return {
        "intent": "action" if tool_name else "question",
        "tool_name": tool_name,
        "tool_args": args,
        "conversational": not tool_name,
        "confidence": 0.9,
    }


STOP = _decision("")  # conversational: no tool


def test_single_tool_turn_runs_tool_then_responds():
    provider = FakeProvider(
        [_decision("molecular_descriptors", smiles="CCO"), STOP, "Ethanol: MW ~46, one hydroxyl."]
    )
    turn = run_chat_turn(
        "Tell me about CCO",
        provider=provider,
        registry=build_default_registry(),
    )
    assert turn.conversational is False
    assert len(turn.steps) == 1
    step = turn.steps[0]
    assert step.tool_name == "molecular_descriptors" and step.ok
    assert step.result["formula"] == "C2H6O"
    assert turn.reply == "Ethanol: MW ~46, one hydroxyl."
    assert turn.messages[-1] == {"role": "assistant", "content": turn.reply}


def test_conversational_turn_calls_no_tool():
    provider = FakeProvider([STOP, "Hi! Ask me about a molecule."])
    turn = run_chat_turn("hello", provider=provider, registry=build_default_registry())
    assert turn.conversational is True
    assert turn.steps == []
    assert turn.reply == "Hi! Ask me about a molecule."


def test_repeated_tool_decision_is_not_rerun():
    # Router keeps asking for the same tool+args; the loop must stop after one.
    provider = FakeProvider(
        [
            _decision("validate_smiles", smiles="CCO"),
            _decision("validate_smiles", smiles="CCO"),
            "Looks valid.",
        ]
    )
    turn = run_chat_turn("check CCO", provider=provider, registry=build_default_registry())
    assert len(turn.steps) == 1


def test_tool_error_stops_loop_and_still_replies():
    provider = FakeProvider([_decision("molecular_descriptors", smiles="not-a-smiles"), "That SMILES is invalid."])
    turn = run_chat_turn("props of not-a-smiles", provider=provider, registry=build_default_registry())
    assert len(turn.steps) == 1 and turn.steps[0].ok is False
    assert turn.reply == "That SMILES is invalid."


def test_empty_responder_falls_back_to_deterministic_summary():
    provider = FakeProvider([_decision("validate_smiles", smiles="CCO"), STOP, ""])
    turn = run_chat_turn("validate CCO", provider=provider, registry=build_default_registry())
    assert "validate_smiles" in turn.reply  # fallback summarized the tool result


def test_max_tool_steps_is_respected():
    # Two distinct tools requested, but max_tool_steps=1 caps it at one.
    provider = FakeProvider(
        [_decision("validate_smiles", smiles="CCO"), _decision("molecular_descriptors", smiles="CCO"), "done"]
    )
    turn = run_chat_turn(
        "validate then describe CCO",
        provider=provider,
        registry=build_default_registry(),
        max_tool_steps=1,
    )
    assert len(turn.steps) == 1
