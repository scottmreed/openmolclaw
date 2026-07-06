"""RDKit tools extraction tests."""
from openmolclaw.chemistry.rdkit_tools import SMILESUtilities, StructureBuilder


def test_canonicalize_is_stable():
    assert SMILESUtilities.canonicalize_smiles("C1=CC=CC=C1") == "c1ccccc1"
    assert SMILESUtilities.canonicalize_smiles("OCC") == SMILESUtilities.canonicalize_smiles("CCO")


def test_validate_smiles_tuple():
    ok, _ = SMILESUtilities.validate_smiles("CCO")
    assert ok is True
    bad_ok, _ = SMILESUtilities.validate_smiles("this is not a molecule")
    assert bad_ok is False


def test_smiles_to_inchi():
    inchi = SMILESUtilities.smiles_to_inchi("CCO")
    assert inchi.startswith("InChI=")


def test_structure_builder_chain_and_ring():
    sb = StructureBuilder()
    chain = sb.build_chain(3)
    assert SMILESUtilities.validate_smiles(chain)[0] is True
    ring = sb.build_ring(6, aromatic=True)
    assert SMILESUtilities.canonicalize_smiles(ring) == "c1ccccc1"
