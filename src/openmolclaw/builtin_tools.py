"""Built-in chemistry tools (OpenMolClaw).

Wires the generic chemistry functions into a :class:`~.harness.tool_registry.ToolRegistry`
so the harness, the Flask app, the chat loop, and ``doctor`` all share one
default tool set. Each tool is a thin, provider-neutral wrapper returning
JSON-safe values.

All tools here are deterministic, local, 2D-graph cheminformatics: validation,
conversion, rendering, descriptors, substructure/SMARTS search, functional-group
detection, and stereochemistry. ``lookup_compound`` is the one tool that can
touch the network (a name→SMILES resolution); the app's Private Structure Mode
gate blocks it when active.

Standard-library + RDKit (+ ``requests`` only if ``lookup_compound`` is called).

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .chemistry import convert, lookup, render, validate
from .harness.tool_registry import ToolRegistry
from .rdkit_agent_tools import register_rdkit_agent_deferred_tools


def _validate_smiles(smiles: str) -> Dict[str, Any]:
    ok, info = validate.validate_smiles_string(smiles)
    return {"valid": ok, "detail": info}


def _render_molecule(smiles: str, width: int = 400, height: int = 300) -> Dict[str, Any]:
    svg = render.render_molecule_svg(smiles, width=width, height=height)
    return {"format": "svg", "svg": svg}


def _convert_smiles(smiles: str) -> Dict[str, Any]:
    cleaned = convert.sanitize_smiles(smiles)
    ok, detail = convert.validate_smiles(cleaned)
    return {"sanitized_smiles": cleaned, "valid": ok, "detail": detail}


def _lookup_compound(name: str) -> Dict[str, Any]:
    return {"name": name, "smiles": lookup.name_to_smiles_or_none(name)}


# --- new: generic 2D RDKit capabilities (no network) ------------------------


def _require_mol(smiles: str):
    """Parse a SMILES to an RDKit mol or raise ValueError (→ tool_error envelope)."""
    from rdkit import Chem

    if not smiles or not str(smiles).strip():
        raise ValueError("empty SMILES string")
    mol = Chem.MolFromSmiles(str(smiles).strip())
    if mol is None:
        raise ValueError(f"invalid SMILES: {smiles!r}")
    return mol


def _molecular_descriptors(smiles: str) -> Dict[str, Any]:
    """Common molecular descriptors for a SMILES (RDKit, deterministic)."""
    from rdkit.Chem import Descriptors, rdMolDescriptors

    mol = _require_mol(smiles)
    return {
        "formula": rdMolDescriptors.CalcMolFormula(mol),
        "molecular_weight": round(Descriptors.MolWt(mol), 3),
        "exact_mass": round(Descriptors.ExactMolWt(mol), 4),
        "logp": round(Descriptors.MolLogP(mol), 3),
        "tpsa": round(Descriptors.TPSA(mol), 3),
        "h_bond_donors": Descriptors.NumHDonors(mol),
        "h_bond_acceptors": Descriptors.NumHAcceptors(mol),
        "rotatable_bonds": Descriptors.NumRotatableBonds(mol),
        "num_rings": rdMolDescriptors.CalcNumRings(mol),
        "num_aromatic_rings": rdMolDescriptors.CalcNumAromaticRings(mol),
        "heavy_atoms": mol.GetNumHeavyAtoms(),
        "formal_charge": sum(a.GetFormalCharge() for a in mol.GetAtoms()),
    }


def _canonicalize_smiles(smiles: str) -> Dict[str, Any]:
    """Return the RDKit canonical SMILES for the input."""
    from rdkit import Chem

    mol = _require_mol(smiles)
    return {"input_smiles": smiles, "canonical_smiles": Chem.MolToSmiles(mol, canonical=True)}


def _to_inchi(smiles: str) -> Dict[str, Any]:
    """Convert a SMILES to InChI + InChIKey."""
    from rdkit.Chem import inchi

    mol = _require_mol(smiles)
    # MolToInchi returns a str in current RDKit, a tuple in older builds.
    raw = inchi.MolToInchi(mol)
    ich = raw[0] if isinstance(raw, tuple) else raw
    return {"inchi": ich, "inchikey": inchi.MolToInchiKey(mol)}


def _substructure_search(smiles: str, smarts: str) -> Dict[str, Any]:
    """Test whether a SMARTS (or SMILES) pattern occurs in a molecule."""
    from rdkit import Chem

    mol = _require_mol(smiles)
    query = Chem.MolFromSmarts(str(smarts)) if smarts else None
    if query is None and smarts:
        query = Chem.MolFromSmiles(str(smarts))
    if query is None:
        raise ValueError(f"invalid query pattern: {smarts!r}")
    matches = mol.GetSubstructMatches(query)
    return {
        "pattern": smarts,
        "matched": bool(matches),
        "match_count": len(matches),
        "atom_indices": [list(m) for m in matches],
    }


# A small, teaching-oriented SMARTS catalog for functional-group detection.
_FUNCTIONAL_GROUP_SMARTS = {
    "hydroxyl": "[#6][OX2H]",
    "carboxylic_acid": "[CX3](=O)[OX2H1]",
    "ester": "[CX3](=O)[OX2H0][#6]",
    "amide": "[NX3][CX3](=[OX1])",
    "aldehyde": "[CX3H1](=O)[#6]",
    "ketone": "[#6][CX3](=O)[#6]",
    "ether": "[OD2]([#6])[#6]",
    "primary_amine": "[NX3;H2;!$(NC=O)]",
    "secondary_amine": "[NX3;H1;!$(NC=O)]",
    "tertiary_amine": "[NX3;H0;!$(NC=O);!$(N=*)]",
    "nitrile": "[NX1]#[CX2]",
    "nitro": "[NX3+](=O)[O-]",
    "thiol": "[#6][SX2H]",
    "alkene": "[CX3]=[CX3]",
    "alkyne": "[CX2]#[CX2]",
    "aromatic_ring": "c1ccccc1",
    "halide": "[F,Cl,Br,I;!$(*[#6]=O)]",
}


def _functional_groups(smiles: str) -> Dict[str, Any]:
    """Detect common functional groups in a molecule via a SMARTS catalog."""
    from rdkit import Chem

    mol = _require_mol(smiles)
    present: List[str] = []
    for name, smarts in _FUNCTIONAL_GROUP_SMARTS.items():
        query = Chem.MolFromSmarts(smarts)
        if query is not None and mol.HasSubstructMatch(query):
            present.append(name)
    return {"functional_groups": present, "count": len(present)}


def _stereochemistry(smiles: str) -> Dict[str, Any]:
    """Report chiral centers (R/S) and stereo double bonds (E/Z)."""
    from rdkit import Chem

    mol = _require_mol(smiles)
    Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
    centers = Chem.FindMolChiralCenters(
        mol, includeUnassigned=True, useLegacyImplementation=False
    )
    chiral = [{"atom_index": idx, "label": label} for idx, label in centers]
    stereo_bonds = 0
    for bond in mol.GetBonds():
        if bond.GetStereo() != Chem.BondStereo.STEREONONE:
            stereo_bonds += 1
    return {
        "chiral_centers": chiral,
        "num_chiral_centers": len(chiral),
        "num_stereo_double_bonds": stereo_bonds,
    }


def build_default_registry(include_deferred_rdkit_agent: bool = True) -> ToolRegistry:
    """Return a registry populated with the built-in chemistry tools.

    ``include_deferred_rdkit_agent`` also registers the optional deferred
    rdkit-agent tool schemas (similarity, atom mapping, reaction balance,
    fingerprints) — see :mod:`openmolclaw.rdkit_agent_tools`. Default ``True``;
    the local Flask app resolves this from ``config["tools"]["rdkit_agent_deferred"]``.
    """
    reg = ToolRegistry()
    _smiles_param = {
        "type": "object",
        "properties": {"smiles": {"type": "string"}},
        "required": ["smiles"],
    }

    reg.register(
        "validate_smiles",
        _validate_smiles,
        description="Validate a SMILES string with RDKit.",
        parameters=_smiles_param,
    )
    reg.register(
        "render_molecule",
        _render_molecule,
        description="Render a molecule (from SMILES) to an SVG string.",
        parameters={
            "type": "object",
            "properties": {
                "smiles": {"type": "string"},
                "width": {"type": "integer"},
                "height": {"type": "integer"},
            },
            "required": ["smiles"],
        },
    )
    reg.register(
        "convert_smiles",
        _convert_smiles,
        description="Sanitize and validate a SMILES string.",
        parameters=_smiles_param,
    )
    reg.register(
        "lookup_compound",
        _lookup_compound,
        description="Resolve a compound name to a SMILES via PubChem.",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    )
    reg.register(
        "molecular_descriptors",
        _molecular_descriptors,
        description=(
            "Compute common molecular descriptors from a SMILES: molecular "
            "formula, weight, exact mass, logP, TPSA, H-bond donors/acceptors, "
            "rotatable bonds, ring counts, heavy atoms, and formal charge."
        ),
        parameters=_smiles_param,
    )
    reg.register(
        "canonicalize_smiles",
        _canonicalize_smiles,
        description="Return the RDKit canonical SMILES for a molecule.",
        parameters=_smiles_param,
    )
    reg.register(
        "to_inchi",
        _to_inchi,
        description="Convert a SMILES to its standard InChI and InChIKey.",
        parameters=_smiles_param,
    )
    reg.register(
        "substructure_search",
        _substructure_search,
        description=(
            "Test whether a SMARTS pattern (or SMILES) occurs in a molecule and "
            "return the matching atom indices."
        ),
        parameters={
            "type": "object",
            "properties": {
                "smiles": {"type": "string"},
                "smarts": {"type": "string"},
            },
            "required": ["smiles", "smarts"],
        },
    )
    reg.register(
        "functional_groups",
        _functional_groups,
        description="Detect common functional groups present in a molecule.",
        parameters=_smiles_param,
    )
    reg.register(
        "stereochemistry",
        _stereochemistry,
        description=(
            "Report chiral centers with R/S labels and the count of E/Z stereo "
            "double bonds for a molecule."
        ),
        parameters=_smiles_param,
    )
    if include_deferred_rdkit_agent:
        register_rdkit_agent_deferred_tools(reg)
    return reg


__all__ = ["build_default_registry"]
