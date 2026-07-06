"""Generic SMILES conversion / cleanup / validation helpers (OpenMolClaw §15.2).

Provider-neutral SMILES sanitization, retro-fragment repair, and validation
lifted from ``app.services.molecule_service.MoleculeService``. These are pure
(standard library + RDKit only) with no product persistence, style-profile, or
project/image coupling, so they belong in the boundary-clean core destined for
the public ``openmolclaw.chemistry`` package.

``MoleculeService`` keeps its static methods as thin delegators to these
functions, so every existing ``MoleculeService.validate_smiles(...)`` /
``sanitize_smiles(...)`` call is unchanged.

Depends only on the standard library + RDKit — standard-library + RDKit only.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Tuple

from rdkit import Chem

try:  # rdBase is optional; log toggling is best-effort only.
    from rdkit import rdBase  # type: ignore
except Exception:  # pragma: no cover - defensive
    rdBase = None


def sanitize_smiles(smiles: str) -> str:
    """Sanitize a SMILES string by trimming whitespace and removing control chars.

    Raises ``ValueError`` if the SMILES is empty or becomes empty after
    sanitization.
    """
    if not smiles:
        raise ValueError("Empty SMILES code provided")

    # Trim whitespace from both ends
    smiles = smiles.strip()

    # Remove any control characters (non-printable characters) but preserve all printable characters
    smiles = ''.join(char for char in smiles if char.isprintable())

    # Trim again after removing control characters
    smiles = smiles.strip()

    if not smiles:
        raise ValueError("Empty SMILES code after sanitization")

    return smiles


def repair_retro_fragment_smiles(smiles: str) -> str:
    """Attempt to repair SMILES codes for retrosynthesis fragments.

    Handles common issues: closes unclosed parentheses, replaces ``*`` wildcards
    with leaving groups (default ``Br``), adds missing atoms when needed, and
    fixes common retrosynthesis patterns.
    """
    if not smiles or not smiles.strip():
        return smiles

    repaired = smiles.strip()

    # Step 1: Replace * wildcards with leaving groups (default to Br)
    # Handle patterns like *O)NCCC or CCC(=*
    if "*" in repaired:
        # Handle *O) pattern
        repaired = repaired.replace("*O)", "BrO)")
        repaired = repaired.replace("*O", "BrO")
        # Handle (=* pattern
        repaired = repaired.replace("(=*", "(=Br")
        repaired = repaired.replace("=*", "=Br")
        # Replace any remaining *
        repaired = repaired.replace("*", "Br")

    # Step 2: Close unclosed parentheses
    open_count = repaired.count("(")
    close_count = repaired.count(")")
    if open_count > close_count:
        # Check for specific patterns that need careful closing
        # Pattern: C(=O or C(=Br needs to become C(=O) or C(=Br)
        if "(=O" in repaired and "(=O)" not in repaired:
            repaired = repaired.replace("(=O", "(=O)", 1)
        elif "(=Br" in repaired and "(=Br)" not in repaired:
            repaired = repaired.replace("(=Br", "(=Br)", 1)

        # Add remaining closing parentheses
        remaining = open_count - close_count
        # Recount after the above fixes
        final_open = repaired.count("(")
        final_close = repaired.count(")")
        if final_open > final_close:
            repaired += ")" * (final_open - final_close)

    # Step 3: Fix invalid patterns like (=Br), (=Cl), (=I) - these are not valid SMILES
    # Replace with proper leaving group attachment (single bond, not double)
    repaired = repaired.replace("(=Br)", "Br")
    repaired = repaired.replace("(=Cl)", "Cl")
    repaired = repaired.replace("(=I)", "I")
    # Also handle unclosed versions
    repaired = repaired.replace("(=Br", "Br")
    repaired = repaired.replace("(=Cl", "Cl")
    repaired = repaired.replace("(=I", "I")

    # Step 4: Handle common retrosynthesis patterns
    # Pattern: C(=O) at the end might need O for carboxylic acid/ester
    if repaired.endswith("(=O)") and "C(=O)O" not in repaired:
        # Check if this is a terminal carbonyl that needs O
        if repaired.count("(=O)") == 1 and repaired.endswith("(=O)"):
            repaired = repaired.replace("(=O)", "(=O)O", 1)

    # Step 5: Fix misplaced parentheses
    # Pattern: BrO)N or BrO)C - the ) might be misplaced
    # Pattern: )NCCC at start - remove the misplaced )
    if repaired.startswith("BrO)") and len(repaired) > 4:
        # Check if the ) is followed by an atom that should be connected
        next_char = repaired[4] if len(repaired) > 4 else ""
        if next_char and next_char.isupper():
            # Remove the misplaced ) - BrO)N should be BrON
            repaired = "BrO" + repaired[4:]
    # Also handle ) at the very start followed by atoms
    if repaired.startswith(")") and len(repaired) > 1 and repaired[1].isupper():
        repaired = repaired[1:]

    # Step 6: Remove double Br (BrBr -> Br)
    repaired = repaired.replace("BrBr", "Br")

    # Final check: ensure parentheses are balanced
    final_open = repaired.count("(")
    final_close = repaired.count(")")
    if final_open > final_close:
        repaired += ")" * (final_open - final_close)

    return repaired


@contextmanager
def suppress_rdkit_parse_logs():
    """Silence RDKit's stderr parse errors/warnings for the duration of a block.

    RDKit prints SMILES parse errors/warnings directly to stderr. For flows that
    routinely validate non-SMILES text (e.g., molecule names), silence RDKit
    parse logging. Best-effort: never fails due to log toggling.
    """
    try:
        if rdBase:
            rdBase.DisableLog("rdApp.error")
            rdBase.DisableLog("rdApp.warning")
        yield
    finally:
        try:
            if rdBase:
                rdBase.EnableLog("rdApp.error")
                rdBase.EnableLog("rdApp.warning")
        except Exception:
            # Best-effort only; never fail due to log toggling.
            pass


def validate_smiles(smiles: str) -> Tuple[bool, str]:
    """Validate a SMILES string. Returns ``(is_valid, error_message)``."""
    try:
        # Sanitize SMILES: trim whitespace and remove control characters
        smiles = sanitize_smiles(smiles)

        # Fast rejects: this method is often used to decide whether a query is SMILES vs a name.
        # Avoid RDKit parse spam for obvious names (e.g., "benzophenone").
        if any(ch.isspace() for ch in smiles):
            # Allow spaces in stereochemical SMILES (e.g., "C1CCCCC1 |c:1,3|")
            # These are valid SMILES with stereochemical information
            parts = smiles.split()
            if len(parts) == 2 and parts[1].startswith('|') and parts[1].endswith('|'):
                # This looks like main SMILES + stereochemical directive, which is valid
                pass  # Allow this through to RDKit validation
            else:
                return False, "SMILES must not contain whitespace"
        if smiles.isalpha() and smiles.islower() and len(smiles) >= 4:
            return False, "Looks like a name, not SMILES"

        with suppress_rdkit_parse_logs():
            mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return False, "Invalid SMILES code"
        return True, ""
    except Exception as e:
        return False, str(e)


def validate_for_model_kit(smiles: str) -> dict:
    """Validate if a molecule meets Model Kit style requirements."""
    try:
        # Sanitize SMILES: trim whitespace and remove control characters
        smiles = sanitize_smiles(smiles)

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {
                "valid": False,
                "error": "Invalid SMILES structure",
            }

        mol_with_h = Chem.AddHs(mol)

        allowed_atoms = {
            "C",
            "N",
            "O",
            "H",
            "F",
            "Cl",
            "Br",
            "S",
            "I",
            "B",
            "P",
        }

        expected_valences = {
            "C": [4],
            "N": [3],
            "O": [2],
            "H": [1],
            "F": [1],
            "Cl": [1],
            "Br": [1],
            "I": [1],
            "S": [2, 4, 6],
            "B": [3],
            "P": [3, 5],
        }

        results = {
            "valid": True,
            "invalid_atoms": [],
            "too_many_atoms": False,
            "atom_count": 0,
            "heavy_atom_count": 0,
            "has_charge": False,
            "valence_errors": [],
        }

        atom_count = mol_with_h.GetNumAtoms()
        results["atom_count"] = atom_count

        heavy_atom_count = mol.GetNumAtoms()
        results["heavy_atom_count"] = heavy_atom_count

        if heavy_atom_count > 15:
            results["valid"] = False
            results["too_many_atoms"] = True

        for atom in mol_with_h.GetAtoms():
            if atom.GetFormalCharge() != 0:
                results["valid"] = False
                results["has_charge"] = True
                break

        for atom in mol_with_h.GetAtoms():
            symbol = atom.GetSymbol()

            if symbol not in allowed_atoms:
                results["valid"] = False
                results["invalid_atoms"].append(symbol)
                continue

            if symbol in expected_valences:
                total_valence = atom.GetTotalValence()
                exp_valences = expected_valences[symbol]
                if total_valence not in exp_valences:
                    results["valid"] = False
                    atom_idx = atom.GetIdx()
                    expected_str = " or ".join(map(str, exp_valences))
                    results["valence_errors"].append(
                        f"{symbol} atom at position {atom_idx} has {total_valence} bonds, expected {expected_str}"
                    )

        results["invalid_atoms"] = list(set(results["invalid_atoms"]))
        return results

    except Exception as e:
        raise ValueError(f"Validation failed: {str(e)}")


__all__ = [
    "sanitize_smiles",
    "repair_retro_fragment_smiles",
    "suppress_rdkit_parse_logs",
    "validate_smiles",
    "validate_for_model_kit",
]
