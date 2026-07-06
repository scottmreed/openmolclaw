"""Deferred rdkit-agent tool schemas (OpenMolClaw).

Advertises selected `rdkit-agent <https://github.com/scottmreed/rdkit-agent>`_
workflows to the LLM as standard provider-neutral tool-call schemas: similarity
search, atom mapping, reaction balance checks, and fingerprints. Every handler
here is a pure, local, deterministic function that returns a structured
"prepared for external execution" envelope — none of them touch the network,
call the CLI, or execute any external processes. Execution of the
prepared request is always deferred to an external agent/runtime that has
``rdkit-agent`` installed.

Standard-library only.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .harness.tool_registry import ToolRegistry

RDKIT_AGENT_REPO = "https://github.com/scottmreed/rdkit-agent"

_SIMILARITY_PARAMS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "query_smiles": {"type": "string"},
        "target_smiles": {"type": "array", "items": {"type": "string"}},
        "threshold": {"type": "number", "default": 0.5},
        "top_n": {"type": "integer", "default": 5},
        "fingerprint": {
            "type": "string",
            "enum": ["morgan", "topological"],
            "default": "morgan",
        },
    },
    "required": ["query_smiles", "target_smiles"],
}

_ATOM_MAP_PARAMS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "operation": {
            "type": "string",
            "enum": ["list", "add", "remove", "check"],
        },
        "smiles": {"type": "string"},
        "smirks": {"type": "string"},
    },
    "required": ["operation"],
}

_REACTION_BALANCE_PARAMS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "reactants": {"type": "array", "items": {"type": "string"}},
        "products": {"type": "array", "items": {"type": "string"}},
        "reaction_smiles": {"type": "string"},
    },
}

_FINGERPRINT_PARAMS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "smiles": {"type": "array", "items": {"type": "string"}},
        "fingerprint": {
            "type": "string",
            "enum": ["morgan", "topological"],
            "default": "morgan",
        },
        "radius": {"type": "integer", "default": 2},
        "n_bits": {"type": "integer", "default": 2048},
    },
    "required": ["smiles"],
}


def _deferred(command: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """The shared "prepared, not executed" envelope every handler returns."""
    return {
        "execution_status": "deferred_external_tool",
        "tool_provider": "rdkit-agent",
        "provider_repo": RDKIT_AGENT_REPO,
        "openmolclaw_executed_cli": False,
        "external_command": command,
        "recommended_cli": f"rdkit-agent {command} --json - --output json",
        "arguments": args,
        "notes": [
            "OpenMolClaw prepared this request as a tool-call payload only.",
            "OpenMolClaw did not run the rdkit-agent CLI.",
            "An external agent/runtime with rdkit-agent installed may execute it.",
        ],
    }


def _similarity_search(
    query_smiles: str,
    target_smiles: List[str],
    threshold: float = 0.5,
    top_n: int = 5,
    fingerprint: str = "morgan",
) -> Dict[str, Any]:
    return _deferred(
        "similarity",
        {
            "query": query_smiles,
            "targets": list(target_smiles),
            "threshold": threshold,
            "top": top_n,
            "fingerprint": fingerprint,
        },
    )


def _atom_map(
    operation: str,
    smiles: Optional[str] = None,
    smirks: Optional[str] = None,
) -> Dict[str, Any]:
    if operation in {"list", "add", "remove"} and not smiles:
        raise ValueError(f"operation {operation!r} requires smiles")
    if operation == "check" and not (smirks or smiles):
        raise ValueError("operation 'check' requires smirks or smiles")
    return _deferred(
        "atom-map",
        {"operation": operation, "smiles": smiles, "smirks": smirks},
    )


def _reaction_balance_check(
    reactants: Optional[List[str]] = None,
    products: Optional[List[str]] = None,
    reaction_smiles: Optional[str] = None,
) -> Dict[str, Any]:
    if not reaction_smiles and not (reactants and products):
        raise ValueError("provide reaction_smiles or both reactants and products")
    return _deferred(
        "balance",
        {
            "reactants": list(reactants or []),
            "products": list(products or []),
            "reaction_smiles": reaction_smiles,
        },
    )


def _fingerprint(
    smiles: List[str],
    fingerprint: str = "morgan",
    radius: int = 2,
    n_bits: int = 2048,
) -> Dict[str, Any]:
    return _deferred(
        "fingerprint",
        {
            "smiles": list(smiles),
            "fingerprint": fingerprint,
            "radius": radius,
            "nBits": n_bits,
        },
    )


def register_rdkit_agent_deferred_tools(reg: ToolRegistry) -> None:
    """Register the four deferred rdkit-agent tools into ``reg``."""
    reg.register(
        "rdkit_agent_similarity_search",
        _similarity_search,
        description=(
            "Prepare a deferred rdkit-agent similarity search request. "
            "OpenMolClaw does not execute the CLI; an external agent/runtime "
            "with rdkit-agent installed may run the returned command."
        ),
        parameters=_SIMILARITY_PARAMS,
    )
    reg.register(
        "rdkit_agent_atom_map",
        _atom_map,
        description=(
            "Prepare a deferred rdkit-agent atom-mapping operation "
            "(list/add/remove/check). OpenMolClaw does not execute the CLI."
        ),
        parameters=_ATOM_MAP_PARAMS,
    )
    reg.register(
        "rdkit_agent_reaction_balance_check",
        _reaction_balance_check,
        description=(
            "Prepare a deferred rdkit-agent reaction balance check from "
            "reactants/products or reaction SMILES/SMIRKS. OpenMolClaw does "
            "not execute the CLI."
        ),
        parameters=_REACTION_BALANCE_PARAMS,
    )
    reg.register(
        "rdkit_agent_fingerprint",
        _fingerprint,
        description=(
            "Prepare a deferred rdkit-agent fingerprint generation request "
            "(Morgan or topological). OpenMolClaw does not execute the CLI."
        ),
        parameters=_FINGERPRINT_PARAMS,
    )


__all__ = ["RDKIT_AGENT_REPO", "register_rdkit_agent_deferred_tools"]
