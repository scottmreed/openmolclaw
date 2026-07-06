"""OpenMolClaw contract tests (shared across repos).

This file — together with ``fixtures/`` and ``expected/`` — is byte-identical in
the public ``openmolclaw`` repo and the private ``chem-art-generator`` repo. It
imports ``binding`` (the ONE per-repo file) to resolve each capability onto that
repo's implementation, then asserts the same fixtures produce the same expected
outputs everywhere.

If a repo has not yet extracted a capability, its binding maps that capability to
``None`` and the corresponding case is skipped; that gap is what the weekly drift
report (PRD §12.3) surfaces. When both repos implement a capability, the outputs
must match to the byte.

Run: ``pytest tests/contract -q`` (public) or the mirror path in the private repo.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from . import binding

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
EXPECTED = HERE / "expected"


def _load(directory: Path, name: str):
    return json.loads((directory / name).read_text(encoding="utf-8"))


def _require(capability: str):
    fn = binding.CAPABILITIES.get(capability)
    if fn is None:
        pytest.skip(f"[{binding.REPO}] capability {capability!r} not implemented yet")
    return fn


# --- router decisions -------------------------------------------------------
def test_router_decisions():
    fn = _require("router_decision")
    inputs = _load(FIXTURES, "router_inputs.json")["cases"]
    expected = _load(EXPECTED, "router_decisions.json")
    for case in inputs:
        got = fn(case["content"])
        assert got == expected[case["name"]], f"router case {case['name']!r} diverged in {binding.REPO}"


# --- schema validation ------------------------------------------------------
def test_schema_validation():
    fn = _require("schema_validation")
    inputs = _load(FIXTURES, "schema_inputs.json")["cases"]
    expected = _load(EXPECTED, "schema_decisions.json")
    for case in inputs:
        got = fn(case["payload"])
        assert got == expected[case["name"]], f"schema case {case['name']!r} diverged in {binding.REPO}"


# --- deterministic RDKit facts ----------------------------------------------
def test_rdkit_facts():
    fn = _require("rdkit_facts")
    inputs = _load(FIXTURES, "smiles_inputs.json")["cases"]
    expected = _load(EXPECTED, "smiles_facts.json")
    for case in inputs:
        got = fn(case["smiles"])
        assert got == expected[case["name"]], f"rdkit case {case['name']!r} diverged in {binding.REPO}"


# --- workspace round-trips --------------------------------------------------
def test_workspace_roundtrip():
    fn = _require("workspace_roundtrip")
    inputs = _load(FIXTURES, "workspace_inputs.json")["cases"]
    expected = _load(EXPECTED, "workspace_roundtrip.json")
    for case in inputs:
        got = fn(case["objects"], case.get("metadata", {}))
        # workspace_id is repo-local; compare only the portable snapshot fields.
        got_cmp = {k: got[k] for k in ("objects", "metadata", "snapshot_version")}
        assert got_cmp == expected[case["name"]], f"workspace case {case['name']!r} diverged in {binding.REPO}"
