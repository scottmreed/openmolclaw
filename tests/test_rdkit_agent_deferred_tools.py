"""Contracts for the deferred rdkit-agent tool schemas (offline, no CLI)."""

from __future__ import annotations

import inspect

import pytest

from openmolclaw.builtin_tools import build_default_registry
from openmolclaw.rdkit_agent_tools import RDKIT_AGENT_REPO

RDKIT_AGENT_TOOL_NAMES = {
    "rdkit_agent_similarity_search",
    "rdkit_agent_atom_map",
    "rdkit_agent_reaction_balance_check",
    "rdkit_agent_fingerprint",
}


@pytest.fixture()
def reg():
    return build_default_registry()


def run(reg, name, **args):
    return reg.get(name).handler(**args)


def test_registry_exposes_deferred_tools(reg):
    assert RDKIT_AGENT_TOOL_NAMES <= set(reg.names())


def test_schemas_use_function_calling_format(reg):
    for name in RDKIT_AGENT_TOOL_NAMES:
        schema = reg.get(name).schema
        assert schema["type"] == "function"
        assert schema["function"]["name"] == name
        assert "does not execute the CLI" in schema["function"]["description"]


def test_similarity_search_returns_deferred_envelope(reg):
    out = run(
        reg,
        "rdkit_agent_similarity_search",
        query_smiles="CCO",
        target_smiles=["CCN", "CCC"],
    )
    assert out["execution_status"] == "deferred_external_tool"
    assert out["tool_provider"] == "rdkit-agent"
    assert out["provider_repo"] == RDKIT_AGENT_REPO
    assert out["openmolclaw_executed_cli"] is False
    assert out["external_command"] == "similarity"
    assert out["arguments"]["query"] == "CCO"
    assert out["arguments"]["targets"] == ["CCN", "CCC"]
    assert out["arguments"]["threshold"] == 0.5
    assert out["arguments"]["top"] == 5


def test_atom_map_requires_smiles_for_list_add_remove(reg):
    with pytest.raises(ValueError):
        run(reg, "rdkit_agent_atom_map", operation="list")
    with pytest.raises(ValueError):
        run(reg, "rdkit_agent_atom_map", operation="add")
    with pytest.raises(ValueError):
        run(reg, "rdkit_agent_atom_map", operation="remove")


def test_atom_map_check_accepts_smirks_only(reg):
    out = run(reg, "rdkit_agent_atom_map", operation="check", smirks="[CH3:1]>>[CH3:1]")
    assert out["execution_status"] == "deferred_external_tool"
    assert out["external_command"] == "atom-map"
    assert out["arguments"]["operation"] == "check"


def test_atom_map_check_requires_smiles_or_smirks(reg):
    with pytest.raises(ValueError):
        run(reg, "rdkit_agent_atom_map", operation="check")


def test_reaction_balance_requires_reaction_or_pair(reg):
    with pytest.raises(ValueError):
        run(reg, "rdkit_agent_reaction_balance_check")
    with pytest.raises(ValueError):
        run(reg, "rdkit_agent_reaction_balance_check", reactants=["CCO"])


def test_reaction_balance_accepts_reaction_smiles(reg):
    out = run(reg, "rdkit_agent_reaction_balance_check", reaction_smiles="CCO>>CC=O")
    assert out["execution_status"] == "deferred_external_tool"
    assert out["arguments"]["reaction_smiles"] == "CCO>>CC=O"


def test_reaction_balance_accepts_reactants_and_products(reg):
    out = run(
        reg,
        "rdkit_agent_reaction_balance_check",
        reactants=["CCO"],
        products=["CC=O"],
    )
    assert out["arguments"]["reactants"] == ["CCO"]
    assert out["arguments"]["products"] == ["CC=O"]


def test_fingerprint_returns_deferred_envelope_with_defaults(reg):
    out = run(reg, "rdkit_agent_fingerprint", smiles=["CCO"])
    assert out["execution_status"] == "deferred_external_tool"
    assert out["external_command"] == "fingerprint"
    assert out["arguments"]["fingerprint"] == "morgan"
    assert out["arguments"]["radius"] == 2
    assert out["arguments"]["nBits"] == 2048


def test_no_handler_shells_out():
    import openmolclaw.rdkit_agent_tools as mod

    src = inspect.getsource(mod)
    for banned in ("subprocess", "os.system", "shutil.which", "Popen"):
        assert banned not in src


def test_registry_can_exclude_deferred_tools():
    reg = build_default_registry(include_deferred_rdkit_agent=False)
    assert not (RDKIT_AGENT_TOOL_NAMES & set(reg.names()))
