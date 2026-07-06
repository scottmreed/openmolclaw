"""Tool registry + shipped skill files tests."""
from pathlib import Path

import openmolclaw
from openmolclaw.builtin_tools import build_default_registry
from openmolclaw.harness.tool_registry import ToolRegistry, normalize_tool_name_for_registry

# Resolve skills from the installed package (src/ layout) so this also verifies
# the skill files actually ship as package data.
SKILLS_DIR = Path(openmolclaw.__file__).resolve().parent / "skills"


def test_normalize_tool_name():
    assert normalize_tool_name_for_registry("functions.render_molecule") == "render_molecule"
    assert normalize_tool_name_for_registry("  validate_smiles ") == "validate_smiles"


def test_register_and_dispatch():
    reg = ToolRegistry()
    reg.register("echo", lambda text: text.upper(), description="upper", parameters={"type": "object"})
    assert reg.has("echo")
    assert reg.get("echo").handler(text="hi") == "HI"
    assert reg.specs()[0]["function"]["name"] == "echo"


def test_default_registry_has_chemistry_tools():
    reg = build_default_registry()
    names = set(reg.names())
    # Original core tools plus the generic 2D RDKit tools exposed to chat.
    assert {"validate_smiles", "render_molecule", "convert_smiles", "lookup_compound"} <= names
    assert {
        "molecular_descriptors",
        "canonicalize_smiles",
        "to_inchi",
        "substructure_search",
        "functional_groups",
        "stereochemistry",
    } <= names
    # every spec is a well-formed function schema
    for spec in reg.specs():
        assert spec["type"] == "function"
        assert "name" in spec["function"]


def test_shipped_skills_present():
    found = sorted(p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md"))
    for required in [
        "rdkit-structure-builder",
        "molecule-svg-drawing",
        "ketcher-local-harness",
        "router-first-tool-calls",
        "workspace-json",
    ]:
        assert required in found
    assert len(found) >= 3  # PRD Phase 1 exit criterion
