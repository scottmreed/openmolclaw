"""OpenMolClaw — an open, local-first chemistry agent harness.

A small, installable package pairing RDKit chemistry tools with a
provider-neutral, router-first agent harness and a local Ketcher + Flask UI.
Point it at a local or OpenRouter-compatible model (e.g. an OLMo-style model),
edit structures in Ketcher, and let the harness validate, render, convert, and
look up molecules into a local workspace.

The public seam (:mod:`openmolclaw.harness.interfaces`) lets a host substitute
its own metering, gating, storage, or model provider without touching harness
code — but everything runs out of the box with local defaults.

Maintained by the ChemIllusion team. Hosted product: https://chemillusion.com
"""

from __future__ import annotations

__version__ = "0.1.0"

from .harness import (
    AllowAllToolGate,
    LocalJSONWorkspaceStore,
    LocalLogUsageSink,
    Router,
    RouterDecision,
    ToolExecutor,
    ToolRegistry,
)
from .harness.interfaces import (
    GateResult,
    ModelProvider,
    ToolContext,
    ToolGate,
    UsageEvent,
    UsageSink,
    Workspace,
    WorkspaceStore,
)
from .workspace import WorkspaceState

__all__ = [
    "__version__",
    # interfaces
    "ModelProvider",
    "UsageSink",
    "ToolGate",
    "WorkspaceStore",
    "UsageEvent",
    "ToolContext",
    "GateResult",
    "Workspace",
    # defaults
    "LocalLogUsageSink",
    "AllowAllToolGate",
    "LocalJSONWorkspaceStore",
    # harness
    "Router",
    "RouterDecision",
    "ToolExecutor",
    "ToolRegistry",
    # workspace
    "WorkspaceState",
]
