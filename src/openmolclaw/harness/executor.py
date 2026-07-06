"""Tool executor (OpenMolClaw harness).

The executor is the second half of the router-first loop. Given a
:class:`~.schemas.RouterDecision` (or a bare tool name + args), it:

1. asks the :class:`~.interfaces.ToolGate` whether the tool may run,
2. dispatches the tool handler from a :class:`~.tool_registry.ToolRegistry`,
3. records a :class:`~.interfaces.UsageEvent` on the :class:`~.interfaces.UsageSink`,
4. normalizes any error into a structured trace entry.

It carries no plan/quota/vendor logic — those attach through the gate and sink
adapters. Standard-library only.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .interfaces import (
    ToolContext,
    ToolGate,
    UsageEvent,
    UsageSink,
)
from .schemas import RouterDecision
from .tool_registry import ToolRegistry, normalize_tool_name_for_registry

logger = logging.getLogger("openmolclaw.harness.executor")


@dataclass
class ToolResult:
    """Outcome of a single tool dispatch, plus a trace-friendly summary."""

    tool_name: str
    ok: bool
    result: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    duration_ms: float = 0.0

    def as_trace(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "ok": self.ok,
            "error": self.error,
            "error_type": self.error_type,
            "duration_ms": round(self.duration_ms, 3),
        }


@dataclass
class ExecutionTrace:
    """Ordered record of tool dispatches for one harness turn."""

    entries: List[Dict[str, Any]] = field(default_factory=list)

    def add(self, result: ToolResult) -> None:
        self.entries.append(result.as_trace())


class ToolExecutor:
    """Dispatches router-selected tools with gating, usage, and tracing."""

    def __init__(
        self,
        registry: ToolRegistry,
        tool_gate: Optional[ToolGate] = None,
        usage_sink: Optional[UsageSink] = None,
    ) -> None:
        self.registry = registry
        self.tool_gate = tool_gate
        self.usage_sink = usage_sink
        self.trace = ExecutionTrace()

    def execute_decision(
        self,
        decision: RouterDecision,
        caller_id: Optional[str] = None,
        surface: Optional[str] = None,
    ) -> ToolResult:
        if decision.conversational or not decision.tool_name:
            result = ToolResult(tool_name="", ok=True, result=None)
            self.trace.add(result)
            return result
        return self.execute(
            decision.tool_name,
            decision.tool_args,
            caller_id=caller_id,
            surface=surface,
        )

    def execute(
        self,
        tool_name: str,
        tool_args: Optional[Dict[str, Any]] = None,
        caller_id: Optional[str] = None,
        surface: Optional[str] = None,
    ) -> ToolResult:
        name = normalize_tool_name_for_registry(tool_name)
        args = dict(tool_args or {})
        started = time.perf_counter()

        # 1) Unknown tool.
        if not self.registry.has(name):
            result = ToolResult(
                tool_name=name,
                ok=False,
                error=f"unknown tool: {name!r}",
                error_type="unknown_tool",
                duration_ms=_ms(started),
            )
            self.trace.add(result)
            return result

        # 2) Gate check.
        if self.tool_gate is not None:
            gate = self.tool_gate.check(
                name, ToolContext(tool_name=name, caller_id=caller_id, surface=surface)
            )
            if not gate.allowed:
                result = ToolResult(
                    tool_name=name,
                    ok=False,
                    error=gate.reason or "tool not allowed",
                    error_type="gate_denied",
                    duration_ms=_ms(started),
                )
                self.trace.add(result)
                return result

        # 3) Dispatch.
        try:
            handler = self.registry.get(name).handler
            value = handler(**args)
            result = ToolResult(
                tool_name=name, ok=True, result=value, duration_ms=_ms(started)
            )
        except TypeError as e:  # bad/missing args
            result = ToolResult(
                tool_name=name,
                ok=False,
                error=str(e),
                error_type="bad_arguments",
                duration_ms=_ms(started),
            )
        except Exception as e:  # noqa: BLE001 - normalized into the trace
            logger.exception("tool %s raised", name)
            result = ToolResult(
                tool_name=name,
                ok=False,
                error=str(e),
                error_type="tool_error",
                duration_ms=_ms(started),
            )

        # 4) Usage.
        if self.usage_sink is not None:
            self.usage_sink.record(
                UsageEvent(kind="tool_call", tool_name=name, metadata={"ok": result.ok})
            )
        self.trace.add(result)
        return result


def _ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000.0


__all__ = ["ToolResult", "ExecutionTrace", "ToolExecutor"]
