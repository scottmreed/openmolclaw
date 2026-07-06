"""Molecule / reaction rendering (OpenMolClaw chemistry).

Deterministic SVG rendering of validated structures via RDKit's
``rdMolDraw2D``. SVG keeps the output text-based and diff-friendly for the local
workspace; PNG is available for callers that need a raster.

Depends only on the standard library and RDKit.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

from typing import Optional

from rdkit import Chem
from rdkit.Chem import rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D


class RenderError(ValueError):
    """Raised when a structure cannot be parsed or rendered."""


def _prepare_mol(smiles: str) -> Chem.Mol:
    mol = Chem.MolFromSmiles((smiles or "").strip())
    if mol is None:
        raise RenderError(f"could not parse SMILES: {smiles!r}")
    rdDepictor.Compute2DCoords(mol)
    return mol


def render_molecule_svg(
    smiles: str,
    width: int = 400,
    height: int = 300,
    *,
    add_stereo_annotation: bool = True,
) -> str:
    """Render a single molecule (from SMILES) to an SVG string."""
    mol = _prepare_mol(smiles)
    drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
    opts = drawer.drawOptions()
    opts.addStereoAnnotation = add_stereo_annotation
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()
    return drawer.GetDrawingText()


def render_reaction_svg(reaction_smiles: str, width: int = 700, height: int = 300) -> str:
    """Render a reaction (``reactants>>products`` SMILES) to an SVG string."""
    rxn = Chem.rdChemReactions.ReactionFromSmarts(
        (reaction_smiles or "").strip(), useSmiles=True
    )
    if rxn is None:
        raise RenderError(f"could not parse reaction SMILES: {reaction_smiles!r}")
    drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
    drawer.DrawReaction(rxn)
    drawer.FinishDrawing()
    return drawer.GetDrawingText()


def render_molecule_png(
    smiles: str, width: int = 400, height: int = 300
) -> bytes:
    """Render a single molecule to PNG bytes (requires a Cairo-enabled RDKit)."""
    mol = _prepare_mol(smiles)
    drawer = rdMolDraw2D.MolDraw2DCairo(width, height)
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()
    return drawer.GetDrawingText()


def molecule_svg_dimensions(svg: str) -> Optional[tuple]:
    """Best-effort (width, height) parse from an SVG header — for tests/tools."""
    import re

    w = re.search(r"width=['\"]?(\d+)", svg)
    h = re.search(r"height=['\"]?(\d+)", svg)
    if w and h:
        return int(w.group(1)), int(h.group(1))
    return None


__all__ = [
    "RenderError",
    "render_molecule_svg",
    "render_reaction_svg",
    "render_molecule_png",
    "molecule_svg_dimensions",
]
