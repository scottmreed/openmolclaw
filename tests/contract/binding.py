"""Contract binding — OpenMolClaw (public package).

The contract suite (``test_contract.py`` + ``fixtures/`` + ``expected/``) is
byte-identical in the public ``openmolclaw`` repo and the private
``chem-art-generator`` repo. Only THIS file differs: it maps the contract's
abstract capabilities onto the concrete modules of the repo it lives in.

Here it targets the public ``openmolclaw`` package, which implements every
capability. The private repo's binding targets ``app.agent_core`` and sets any
capability it has not yet extracted to ``None`` (the contract case then skips,
and the gap shows up in the weekly drift report — PRD §12.3).

A capability is "available" when its callable is not ``None``.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from rdkit import Chem

from openmolclaw.chemistry.rdkit_tools import SMILESUtilities
from openmolclaw.harness.router import Router, parse_router_json_content
from openmolclaw.harness.schemas import RouterDecision
from openmolclaw.workspace.serialization import from_snapshot, to_snapshot
from openmolclaw.workspace.state import WorkspaceState

REPO = "openmolclaw"

_DECISION_KEYS = ("intent", "tool_name", "tool_args", "conversational")


def decision_from_content(content: str) -> Dict[str, Any]:
    """Parse router JSON, build a decision, return the shared field subset."""
    payload = parse_router_json_content(content)
    decision = Router.decision_from_payload(payload)
    return {k: getattr(decision, k) for k in _DECISION_KEYS}


def validate_decision(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a RouterDecision payload; return the shared field subset."""
    decision = RouterDecision(**payload)
    out = {k: getattr(decision, k) for k in _DECISION_KEYS}
    out["confidence"] = decision.confidence
    return out


def smiles_facts(smiles: str) -> Dict[str, Optional[str]]:
    """Deterministic RDKit-derived facts for a SMILES string."""
    canonical = SMILESUtilities.canonicalize_smiles(smiles)
    inchi = SMILESUtilities.smiles_to_inchi(smiles)
    inchikey = Chem.InchiToInchiKey(inchi) if inchi else None
    return {"canonical": canonical, "inchikey": inchikey}


def workspace_roundtrip(objects: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Round-trip a workspace through the snapshot serializer."""
    state = WorkspaceState.new("contract")
    state.workspace.objects.update(objects)
    state.workspace.metadata.update(metadata)
    restored = from_snapshot(to_snapshot(state.workspace))
    return to_snapshot(restored)


# Capability map. ``None`` => not implemented in this repo (contract case skips).
CAPABILITIES: Dict[str, Optional[Callable[..., Any]]] = {
    "router_decision": decision_from_content,
    "schema_validation": validate_decision,
    "rdkit_facts": smiles_facts,
    "workspace_roundtrip": workspace_roundtrip,
}
