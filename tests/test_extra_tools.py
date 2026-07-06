"""Contracts for the added generic 2D RDKit tools (offline, deterministic)."""

from __future__ import annotations

import pytest

from openmolclaw.builtin_tools import build_default_registry


@pytest.fixture()
def reg():
    return build_default_registry()


def run(reg, name, **args):
    return reg.get(name).handler(**args)


def test_registry_exposes_new_tools(reg):
    names = set(reg.names())
    assert {
        "molecular_descriptors",
        "canonicalize_smiles",
        "to_inchi",
        "substructure_search",
        "functional_groups",
        "stereochemistry",
    } <= names


def test_molecular_descriptors_ethanol(reg):
    d = run(reg, "molecular_descriptors", smiles="CCO")
    assert d["formula"] == "C2H6O"
    assert round(d["molecular_weight"]) == 46
    assert d["h_bond_donors"] == 1


def test_canonicalize_is_stable(reg):
    a = run(reg, "canonicalize_smiles", smiles="OCC")["canonical_smiles"]
    b = run(reg, "canonicalize_smiles", smiles="CCO")["canonical_smiles"]
    assert a == b == "CCO"


def test_to_inchi_ethanol(reg):
    out = run(reg, "to_inchi", smiles="CCO")
    assert out["inchi"].startswith("InChI=1S/C2H6O")
    assert out["inchikey"].startswith("LFQSCWFLJHTTHZ")


def test_substructure_search_finds_carbonyl(reg):
    out = run(reg, "substructure_search", smiles="CC(=O)O", smarts="[CX3]=O")
    assert out["matched"] is True and out["match_count"] >= 1


def test_functional_groups_acetic_acid(reg):
    out = run(reg, "functional_groups", smiles="CC(=O)O")
    assert "carboxylic_acid" in out["functional_groups"]


def test_stereochemistry_reports_chiral_center(reg):
    out = run(reg, "stereochemistry", smiles="C[C@H](N)C(=O)O")  # L-alanine
    assert out["num_chiral_centers"] == 1
    assert out["chiral_centers"][0]["label"] in ("R", "S")


def test_invalid_smiles_raises(reg):
    with pytest.raises(ValueError):
        run(reg, "molecular_descriptors", smiles="not-a-smiles")
