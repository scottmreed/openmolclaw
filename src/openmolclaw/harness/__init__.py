"""OpenMolClaw harness — provider-neutral router-first orchestration.

Exposes the adapter interfaces and public-safe defaults, the router/executor
loop, the tool registry, and the schema envelopes. Model providers live in
``openmolclaw.harness.providers``.
"""

from __future__ import annotations

from .defaults import AllowAllToolGate, LocalJSONWorkspaceStore, LocalLogUsageSink
from .executor import ExecutionTrace, ToolExecutor, ToolResult
from .interfaces import (
    GateResult,
    Message,
    ModelProvider,
    ToolContext,
    ToolGate,
    ToolSpec,
    UsageEvent,
    UsageSink,
    Workspace,
    WorkspaceStore,
)
from .router import Router, parse_router_json_content
from .schemas import RouterDecision
from .tool_registry import RegisteredTool, ToolRegistry, normalize_tool_name_for_registry

__all__ = [
    "ModelProvider",
    "UsageSink",
    "ToolGate",
    "WorkspaceStore",
    "Message",
    "ToolSpec",
    "UsageEvent",
    "ToolContext",
    "GateResult",
    "Workspace",
    "LocalLogUsageSink",
    "AllowAllToolGate",
    "LocalJSONWorkspaceStore",
    "Router",
    "parse_router_json_content",
    "RouterDecision",
    "ToolExecutor",
    "ToolResult",
    "ExecutionTrace",
    "ToolRegistry",
    "RegisteredTool",
    "normalize_tool_name_for_registry",
]
