"""Generic SMILES validation (OpenMolClaw project).

Provider-neutral chemistry validation with no product or billing coupling. Depends only on the standard library and RDKit — standard-library + RDKit only.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

import re
from typing import Tuple

# Natural-language fragments that indicate a SMILES string was corrupted with
# prose (a common failure mode when a model inlines explanation into a value).
_CORRUPTION_PATTERNS = (
    "your molecule",
    "my molecule",
    "the molecule",
    "this molecule",
    "parent compound",
    "reference",
    "original",
    " is ",
    " has ",
    " with ",
    " and ",
    " or ",
    " the ",
)

# Valid SMILES characters: A-Z a-z 0-9 @ + - [ ] ( ) = # $ % \ / : .
_VALID_SMILES_RE = re.compile(r"^[A-Za-z0-9@+\-\[\]\(\)=#$%\\/:.]+$")
_VALID_CHAR_RE = re.compile(r"[A-Za-z0-9@+\-\[\]\(\)=#$%\\/:.]")


def validate_smiles_string(smiles: str) -> Tuple[bool, str]:
    """Validate a SMILES string.

    Returns ``(is_valid, cleaned_smiles_or_error)``. Rejects strings corrupted
    with natural-language text, strings with invalid characters, and strings
    RDKit cannot parse.
    """
    if not smiles or not isinstance(smiles, str):
        return False, "Empty or invalid SMILES"

    smiles = smiles.strip()

    smiles_lower = smiles.lower()
    for pattern in _CORRUPTION_PATTERNS:
        if pattern in smiles_lower:
            return False, f"SMILES appears corrupted - contains text '{pattern}'"

    if not _VALID_SMILES_RE.match(smiles):
        invalid_chars = set(c for c in smiles if not _VALID_CHAR_RE.match(c))
        return False, f"SMILES contains invalid characters: {invalid_chars}"

    try:
        from rdkit import Chem

        from .convert import suppress_rdkit_parse_logs

        # Validation is routinely called on possibly-invalid input; don't let
        # RDKit spew parse errors to stderr for the expected-failure case.
        with suppress_rdkit_parse_logs():
            mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return False, "RDKit failed to parse SMILES"
        return True, smiles
    except Exception as e:  # pragma: no cover - defensive
        return False, f"SMILES validation error: {str(e)}"


__all__ = ["validate_smiles_string"]
