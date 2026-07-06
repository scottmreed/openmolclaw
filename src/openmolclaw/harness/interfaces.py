"""OpenMolClaw — adapter interfaces (the public seam).

These Protocols define the boundary between the generic chemistry-agent harness
and any host-specific implementations a downstream deployment might supply.
OpenMolClaw ships public-safe defaults for every one of them (see
``defaults.py``); a hosted product can substitute its own metering, gating,
storage, or model-provider implementations behind the same interface without
changing harness code.

Design rules:

* This module depends only on the Python standard library. It names no model
  vendor and no hosting backend — those live behind the interface, never inside
  it. That keeps the harness portable and the package installable with nothing
  but the scientific dependencies.
* The public defaults are no-op / local-file equivalents: log usage instead of
  metering it, allow every tool, and persist workspaces to local JSON.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    runtime_checkable,
)

# ---------------------------------------------------------------------------
# Shared value types
# ---------------------------------------------------------------------------

# A chat message in provider-neutral form, e.g. ``{"role": "user", "content": "..."}``.
Message = Dict[str, Any]

# A tool/function schema in provider-neutral (function-calling) form.
ToolSpec = Dict[str, Any]


@dataclass(frozen=True)
class UsageEvent:
    """A single token/tool usage event emitted by the harness.

    The harness produces these; a :class:`UsageSink` decides what to do with
    them. The public default simply logs; a host may record them against its
    own metering.
    """

    kind: str  # e.g. "model_call", "tool_call"
    model: Optional[str] = None
    tool_name: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolContext:
    """Context handed to a :class:`ToolGate` when deciding whether a tool may run.

    The harness populates only generic fields. A host gate may read additional
    data it attaches via ``extra`` (e.g. a caller's plan or quota), but the
    public package never assumes those keys exist.
    """

    tool_name: str
    caller_id: Optional[str] = None
    surface: Optional[str] = None
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GateResult:
    """Result of a :class:`ToolGate` check."""

    allowed: bool
    reason: Optional[str] = None

    @classmethod
    def allow(cls) -> "GateResult":
        return cls(allowed=True)

    @classmethod
    def deny(cls, reason: str) -> "GateResult":
        return cls(allowed=False, reason=reason)


@dataclass
class Workspace:
    """A local, provider-neutral workspace state container.

    Holds molecules / reactions / labels / rendered assets keyed by their
    semantic aliases (``[m1]``, ``[r1]``, ``[label1]``). The public default
    persists this as a local JSON file; a host may persist it to its own
    project/canvas storage.
    """

    workspace_id: str
    objects: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Adapter Protocols (the public seam)
# ---------------------------------------------------------------------------


@runtime_checkable
class ModelProvider(Protocol):
    """Completes a chat request with forced/optional tool calling.

    Public implementations: a local chat-completions-compatible endpoint and an
    OpenRouter-compatible endpoint (see ``providers/``). A host may add its own
    provider behind this same interface.
    """

    def complete_with_tools(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        tool_choice: Any = None,
    ) -> Any:
        ...


@runtime_checkable
class UsageSink(Protocol):
    """Receives token/tool usage events.

    Public default: no-op / local log (see ``defaults.LocalLogUsageSink``).
    """

    def record(self, event: UsageEvent) -> None:
        ...


@runtime_checkable
class ToolGate(Protocol):
    """Decides whether a tool may run for this caller.

    Public default: allow everything (see ``defaults.AllowAllToolGate``). A host
    may enforce its own access rules behind this interface.
    """

    def check(self, tool_name: str, context: ToolContext) -> GateResult:
        ...


@runtime_checkable
class WorkspaceStore(Protocol):
    """Persists workspace state.

    Public default: local JSON file (see ``defaults.LocalJSONWorkspaceStore``).
    """

    def load(self, workspace_id: str) -> Workspace:
        ...

    def save(self, workspace: Workspace) -> None:
        ...


__all__ = [
    "Message",
    "ToolSpec",
    "UsageEvent",
    "ToolContext",
    "GateResult",
    "Workspace",
    "ModelProvider",
    "UsageSink",
    "ToolGate",
    "WorkspaceStore",
]
