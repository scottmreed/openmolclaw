# Optional `rdkit-agent` Deferred Tool-Calling Surface — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four `rdkit_agent_*` tool schemas to OpenMolClaw's tool registry that prepare structured, deferred `rdkit-agent` CLI invocation payloads (similarity search, atom mapping, reaction balance check, fingerprint) without ever executing the CLI, expose them through the existing `/api/tools`, `/api/execute`, and `/api/chat` surfaces, add a frontend section that routes user input through the chat model as a normal tool call, and document the feature.

**Architecture:** A new `src/openmolclaw/rdkit_agent_tools.py` module registers four handlers into the existing provider-neutral `ToolRegistry` (same pattern as `builtin_tools.py`). Every handler returns the same `execution_status: "deferred_external_tool"` envelope — pure Python, JSON-safe, zero I/O. `build_default_registry()` gains an `include_deferred_rdkit_agent: bool = True` flag; `app.py` resolves that flag from `config["tools"]["rdkit_agent_deferred"]` (default `True`) using the existing `coerce_bool` helper. The frontend adds one small form that builds a chat prompt naming the tool and submits it through the existing `/api/chat` flow — no new endpoint, no direct tool execution from JS.

**Tech Stack:** Python 3.10+, Flask, pytest, vanilla JS/CSS (no build step) — matches the existing stack exactly, no new dependencies.

## Global Constraints

- Never import or call `subprocess`, `os.system`, `shutil.which`, `npm`, `npx`, or the `rdkit-agent` CLI anywhere in `openmolclaw` source. (PRD §4, §14)
- No `npm`/`node`/`@rdkit/rdkit`/`rdkit-agent` entries in `pyproject.toml`. (PRD §4, §14)
- Every deferred handler returns the exact envelope shape from PRD §7.2 (`execution_status`, `tool_provider`, `provider_repo`, `openmolclaw_executed_cli: False`, `external_command`, `recommended_cli`, `arguments`, `notes`).
- Tool name prefix is `rdkit_agent_*` (not `external_rdkit_*`). (PRD §17)
- Config flag is `tools.rdkit_agent_deferred`, default `True`. (PRD §17)
- `/api/execute` and `/api/tools/<name>` keep returning HTTP `200` for a successful deferred-tool call — deferred tools are not a distinct HTTP status class. (PRD §17)
- Chat responder must say "prepared"/"deferred", never "computed"/"ran"/"executed" — this is steered via the tool's own `notes` field and description text, not a responder-prompt rewrite (the responder already only summarizes what a tool returned; see `harness/chat.py:42-51`).
- `docs/rdkit_agent_deferred_tools.md` must link to `https://github.com/scottmreed/rdkit-agent`. (PRD §12)
- Follow existing repo style: `from __future__ import annotations`, `Optional[X]` (not `X | None`), module docstring naming "OpenMolClaw" and "Maintained by the ChemIllusion team as part of the OpenMolClaw project."

---

### Task 1: Deferred `rdkit-agent` tool module + registry wiring

**Files:**
- Create: `src/openmolclaw/rdkit_agent_tools.py`
- Modify: `src/openmolclaw/builtin_tools.py:177-179` (function signature + registration call), `:1-24` (import)
- Modify: `src/openmolclaw/contracts/checks.py:117-128` (`_EXPECTED_TOOLS` — the in-package contract suite hardcodes the tool-name set and will otherwise fail as soon as the registry grows)
- Test: `tests/test_rdkit_agent_deferred_tools.py`

**Interfaces:**
- Consumes: `openmolclaw.harness.tool_registry.ToolRegistry.register(name, handler, *, description, parameters)` (existing, `src/openmolclaw/harness/tool_registry.py:50-75`).
- Produces: `register_rdkit_agent_deferred_tools(reg: ToolRegistry) -> None` and `RDKIT_AGENT_REPO: str`, importable as `from openmolclaw.rdkit_agent_tools import register_rdkit_agent_deferred_tools, RDKIT_AGENT_REPO`. Registers tool names `rdkit_agent_similarity_search`, `rdkit_agent_atom_map`, `rdkit_agent_reaction_balance_check`, `rdkit_agent_fingerprint`. `build_default_registry(include_deferred_rdkit_agent: bool = True) -> ToolRegistry` (modified signature, default preserves current callers).

**Gotcha found during planning:** `src/openmolclaw/contracts/checks.py:117-134` defines `check_tool_schema_shape()`, which asserts `{s["function"]["name"] for s in build_default_registry().specs()} == _EXPECTED_TOOLS` — a hardcoded 10-name set. This runs as part of `run_contracts()`, which backs `/api/contracts`, `openmolclaw doctor`, `openmolclaw run-contracts`, and `tests/test_contracts_runner.py::test_all_contracts_pass`. Since `build_default_registry()` defaults to including the 4 new tools, this assertion breaks the moment Task 1 lands unless `_EXPECTED_TOOLS` is updated in the same commit (Step 4a below). This file is public-owned in-package code (not the synced `tests/contract/` cross-repo suite), so it is safe to edit directly.

- [ ] **Step 1: Write the failing test file**

Create `tests/test_rdkit_agent_deferred_tools.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_rdkit_agent_deferred_tools.py -v`
Expected: FAIL/ERROR — `ModuleNotFoundError: No module named 'openmolclaw.rdkit_agent_tools'`.

- [ ] **Step 3: Create `src/openmolclaw/rdkit_agent_tools.py`**

```python
"""Deferred rdkit-agent tool schemas (OpenMolClaw).

Advertises selected `rdkit-agent <https://github.com/scottmreed/rdkit-agent>`_
workflows to the LLM as standard provider-neutral tool-call schemas: similarity
search, atom mapping, reaction balance checks, and fingerprints. Every handler
here is a pure, local, deterministic function that returns a structured
"prepared for external execution" envelope — none of them touch the network,
spawn a subprocess, or execute the ``rdkit-agent`` CLI. Execution of the
prepared request is always deferred to an external agent/runtime that has
``rdkit-agent`` installed.

Standard-library only.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .harness.tool_registry import ToolRegistry

RDKIT_AGENT_REPO = "https://github.com/scottmreed/rdkit-agent"

_SIMILARITY_PARAMS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "query_smiles": {"type": "string"},
        "target_smiles": {"type": "array", "items": {"type": "string"}},
        "threshold": {"type": "number", "default": 0.5},
        "top_n": {"type": "integer", "default": 5},
        "fingerprint": {
            "type": "string",
            "enum": ["morgan", "topological"],
            "default": "morgan",
        },
    },
    "required": ["query_smiles", "target_smiles"],
}

_ATOM_MAP_PARAMS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "operation": {
            "type": "string",
            "enum": ["list", "add", "remove", "check"],
        },
        "smiles": {"type": "string"},
        "smirks": {"type": "string"},
    },
    "required": ["operation"],
}

_REACTION_BALANCE_PARAMS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "reactants": {"type": "array", "items": {"type": "string"}},
        "products": {"type": "array", "items": {"type": "string"}},
        "reaction_smiles": {"type": "string"},
    },
}

_FINGERPRINT_PARAMS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "smiles": {"type": "array", "items": {"type": "string"}},
        "fingerprint": {
            "type": "string",
            "enum": ["morgan", "topological"],
            "default": "morgan",
        },
        "radius": {"type": "integer", "default": 2},
        "n_bits": {"type": "integer", "default": 2048},
    },
    "required": ["smiles"],
}


def _deferred(command: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """The shared "prepared, not executed" envelope every handler returns."""
    return {
        "execution_status": "deferred_external_tool",
        "tool_provider": "rdkit-agent",
        "provider_repo": RDKIT_AGENT_REPO,
        "openmolclaw_executed_cli": False,
        "external_command": command,
        "recommended_cli": f"rdkit-agent {command} --json - --output json",
        "arguments": args,
        "notes": [
            "OpenMolClaw prepared this request as a tool-call payload only.",
            "OpenMolClaw did not run the rdkit-agent CLI.",
            "An external agent/runtime with rdkit-agent installed may execute it.",
        ],
    }


def _similarity_search(
    query_smiles: str,
    target_smiles: List[str],
    threshold: float = 0.5,
    top_n: int = 5,
    fingerprint: str = "morgan",
) -> Dict[str, Any]:
    return _deferred(
        "similarity",
        {
            "query": query_smiles,
            "targets": list(target_smiles),
            "threshold": threshold,
            "top": top_n,
            "fingerprint": fingerprint,
        },
    )


def _atom_map(
    operation: str,
    smiles: Optional[str] = None,
    smirks: Optional[str] = None,
) -> Dict[str, Any]:
    if operation in {"list", "add", "remove"} and not smiles:
        raise ValueError(f"operation {operation!r} requires smiles")
    if operation == "check" and not (smirks or smiles):
        raise ValueError("operation 'check' requires smirks or smiles")
    return _deferred(
        "atom-map",
        {"operation": operation, "smiles": smiles, "smirks": smirks},
    )


def _reaction_balance_check(
    reactants: Optional[List[str]] = None,
    products: Optional[List[str]] = None,
    reaction_smiles: Optional[str] = None,
) -> Dict[str, Any]:
    if not reaction_smiles and not (reactants and products):
        raise ValueError("provide reaction_smiles or both reactants and products")
    return _deferred(
        "balance",
        {
            "reactants": list(reactants or []),
            "products": list(products or []),
            "reaction_smiles": reaction_smiles,
        },
    )


def _fingerprint(
    smiles: List[str],
    fingerprint: str = "morgan",
    radius: int = 2,
    n_bits: int = 2048,
) -> Dict[str, Any]:
    return _deferred(
        "fingerprint",
        {
            "smiles": list(smiles),
            "fingerprint": fingerprint,
            "radius": radius,
            "nBits": n_bits,
        },
    )


def register_rdkit_agent_deferred_tools(reg: ToolRegistry) -> None:
    """Register the four deferred rdkit-agent tools into ``reg``."""
    reg.register(
        "rdkit_agent_similarity_search",
        _similarity_search,
        description=(
            "Prepare a deferred rdkit-agent similarity search request. "
            "OpenMolClaw does not execute the CLI; an external agent/runtime "
            "with rdkit-agent installed may run the returned command."
        ),
        parameters=_SIMILARITY_PARAMS,
    )
    reg.register(
        "rdkit_agent_atom_map",
        _atom_map,
        description=(
            "Prepare a deferred rdkit-agent atom-mapping operation "
            "(list/add/remove/check). OpenMolClaw does not execute the CLI."
        ),
        parameters=_ATOM_MAP_PARAMS,
    )
    reg.register(
        "rdkit_agent_reaction_balance_check",
        _reaction_balance_check,
        description=(
            "Prepare a deferred rdkit-agent reaction balance check from "
            "reactants/products or reaction SMILES/SMIRKS. OpenMolClaw does "
            "not execute the CLI."
        ),
        parameters=_REACTION_BALANCE_PARAMS,
    )
    reg.register(
        "rdkit_agent_fingerprint",
        _fingerprint,
        description=(
            "Prepare a deferred rdkit-agent fingerprint generation request "
            "(Morgan or topological). OpenMolClaw does not execute the CLI."
        ),
        parameters=_FINGERPRINT_PARAMS,
    )


__all__ = ["RDKIT_AGENT_REPO", "register_rdkit_agent_deferred_tools"]
```

- [ ] **Step 4: Wire registration into `build_default_registry`**

In `src/openmolclaw/builtin_tools.py`, add the import (line 24, right after the existing relative imports):

```python
from .chemistry import convert, lookup, render, validate
from .harness.tool_registry import ToolRegistry
from .rdkit_agent_tools import register_rdkit_agent_deferred_tools
```

Then change the function signature and final block (currently `src/openmolclaw/builtin_tools.py:177-276`):

```python
def build_default_registry(include_deferred_rdkit_agent: bool = True) -> ToolRegistry:
    """Return a registry populated with the built-in chemistry tools.

    ``include_deferred_rdkit_agent`` also registers the optional deferred
    rdkit-agent tool schemas (similarity, atom mapping, reaction balance,
    fingerprints) — see :mod:`openmolclaw.rdkit_agent_tools`. Default ``True``;
    the local Flask app resolves this from ``config["tools"]["rdkit_agent_deferred"]``.
    """
    reg = ToolRegistry()
```

... (existing body unchanged) ...

Replace the final `return reg` with:

```python
    if include_deferred_rdkit_agent:
        register_rdkit_agent_deferred_tools(reg)
    return reg
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_rdkit_agent_deferred_tools.py -v`
Expected: all tests PASS.

- [ ] **Step 6: Run the full offline suite — confirm the contract-suite drift check**

Run: `pytest tests/test_contracts_runner.py -v`
Expected: FAIL — `test_all_contracts_pass` fails with `AssertionError: tool set drifted: [...14 names including the 4 new ones...]`, from `check_tool_schema_shape()` in `src/openmolclaw/contracts/checks.py:134`. This confirms the gotcha above is real before fixing it.

- [ ] **Step 6a: Update `_EXPECTED_TOOLS` in `src/openmolclaw/contracts/checks.py`**

Replace `src/openmolclaw/contracts/checks.py:117-128`:

```python
_EXPECTED_TOOLS = {
    "validate_smiles",
    "render_molecule",
    "convert_smiles",
    "lookup_compound",
    "molecular_descriptors",
    "canonicalize_smiles",
    "to_inchi",
    "substructure_search",
    "functional_groups",
    "stereochemistry",
    "rdkit_agent_similarity_search",
    "rdkit_agent_atom_map",
    "rdkit_agent_reaction_balance_check",
    "rdkit_agent_fingerprint",
}
```

- [ ] **Step 6b: Run the full offline suite to confirm it now passes**

Run: `pytest -q`
Expected: PASS. (`tests/test_app_endpoints.py::test_list_tools` in `tests/test_app_endpoints.py:54-68` will still fail here with the old hardcoded 10-name set — that assertion is fixed in Task 2, Step 1. Every other test, including `test_contracts_runner.py` and `test_rdkit_agent_deferred_tools.py`, should pass.)

- [ ] **Step 7: Commit**

```bash
git add src/openmolclaw/rdkit_agent_tools.py src/openmolclaw/builtin_tools.py src/openmolclaw/contracts/checks.py tests/test_rdkit_agent_deferred_tools.py
git commit -m "feat: add deferred rdkit-agent tool schemas and handlers"
```

---

### Task 2: Config flag + `/api/tools`, `/api/execute`, `/api/chat` exposure

**Files:**
- Modify: `src/openmolclaw/app.py:52-73` (import), `:129-130` (registry construction)
- Modify: `tests/test_app_endpoints.py:54-68` (`test_list_tools` expected set)
- Test: append new cases to `tests/test_app_endpoints.py` and `tests/test_app_chat.py`

**Interfaces:**
- Consumes: `coerce_bool(value, *, env, default) -> bool` (existing, `src/openmolclaw/privacy.py:43-62`), `build_default_registry(include_deferred_rdkit_agent: bool = True)` (Task 1).
- Produces: `create_app(config={"tools": {"rdkit_agent_deferred": False}})` disables the four tools; `OPENMOLCLAW_TOOLS_RDKIT_AGENT_DEFERRED` env var as a fallback when the config key is unset.

- [ ] **Step 1: Update `test_list_tools` (currently failing after Task 1) and add new failing tests**

In `tests/test_app_endpoints.py`, replace the body of `test_list_tools` (`tests/test_app_endpoints.py:54-68`):

```python
def test_list_tools(client):
    body = client.get("/api/tools").get_json()
    names = {s["function"]["name"] for s in body["tools"]}
    assert names == {
        "validate_smiles",
        "render_molecule",
        "convert_smiles",
        "lookup_compound",
        "molecular_descriptors",
        "canonicalize_smiles",
        "to_inchi",
        "substructure_search",
        "functional_groups",
        "stereochemistry",
        "rdkit_agent_similarity_search",
        "rdkit_agent_atom_map",
        "rdkit_agent_reaction_balance_check",
        "rdkit_agent_fingerprint",
    }
```

Then append these new tests at the end of `tests/test_app_endpoints.py`:

```python
def test_execute_each_deferred_rdkit_agent_tool(client):
    cases = [
        (
            "rdkit_agent_similarity_search",
            {"query_smiles": "CCO", "target_smiles": ["CCN"]},
        ),
        ("rdkit_agent_atom_map", {"operation": "check", "smirks": "[CH3:1]>>[CH3:1]"}),
        (
            "rdkit_agent_reaction_balance_check",
            {"reaction_smiles": "CCO>>CC=O"},
        ),
        ("rdkit_agent_fingerprint", {"smiles": ["CCO"]}),
    ]
    for tool, args in cases:
        r = client.post("/api/execute", json={"tool": tool, "args": args})
        assert r.status_code == 200, tool
        body = r.get_json()
        assert body["ok"] is True, tool
        assert body["result"]["execution_status"] == "deferred_external_tool", tool
        assert body["result"]["openmolclaw_executed_cli"] is False, tool


def test_deferred_rdkit_agent_tools_can_be_disabled_via_config(tmp_path):
    from openmolclaw.app import create_app
    from openmolclaw.harness.defaults import LocalJSONWorkspaceStore

    store = LocalJSONWorkspaceStore(root=tmp_path / "ws")
    app = create_app(store=store, config={"tools": {"rdkit_agent_deferred": False}})
    app.testing = True
    disabled_client = app.test_client()
    names = {s["function"]["name"] for s in disabled_client.get("/api/tools").get_json()["tools"]}
    assert "rdkit_agent_similarity_search" not in names
    r = disabled_client.post(
        "/api/execute", json={"tool": "rdkit_agent_similarity_search", "args": {}}
    )
    assert r.get_json()["error_type"] == "unknown_tool"
```

Append this test to `tests/test_app_chat.py` (after `test_chat_private_structure_mode_blocks_lookup`):

```python
def test_chat_routes_to_deferred_rdkit_agent_tool(tmp_path):
    factory = lambda cfg: FakeProvider(  # noqa: E731
        [
            _decision(
                "rdkit_agent_similarity_search",
                query_smiles="CCO",
                target_smiles=["CCN"],
            ),
            STOP,
            "I prepared a deferred rdkit-agent similarity search. OpenMolClaw did not run the CLI.",
        ]
    )
    client = _client(tmp_path, provider_factory=factory)
    r = client.post("/api/chat", json={"message": "compare CCO to CCN", "history": []})
    body = r.get_json()
    assert body["ok"] is True
    step = next(s for s in body["steps"] if s["tool_name"] == "rdkit_agent_similarity_search")
    assert step["ok"] is True
    assert step["result"]["execution_status"] == "deferred_external_tool"
    assert "did not run the CLI" in body["reply"]
    # Deferred payloads are not molecules — no workspace object should be created.
    assert body["workspace"] == []
```

- [ ] **Step 2: Run the new/updated tests to verify they fail**

Run: `pytest tests/test_app_endpoints.py tests/test_app_chat.py -v`
Expected: `test_list_tools`, `test_execute_each_deferred_rdkit_agent_tool`, `test_deferred_rdkit_agent_tools_can_be_disabled_via_config`, and `test_chat_routes_to_deferred_rdkit_agent_tool` FAIL — the registry always includes the tools (no config gate yet) and/or the config flag doesn't exist yet. (`test_chat_routes_to_deferred_rdkit_agent_tool` may already pass since Task 1 already wired the tools in by default — that's fine, it becomes a regression guard.)

- [ ] **Step 3: Wire the config flag in `app.py`**

Add `coerce_bool` to the existing `.privacy` import (`src/openmolclaw/app.py:68-72`):

```python
from .privacy import (
    StructureRedactingLogFilter,
    coerce_bool,
    describe_privacy,
    resolve_workspace_save_mode,
)
```

Replace the registry construction line (`src/openmolclaw/app.py:130`, currently `registry = build_default_registry()`) with:

```python
    tools_cfg = (cfg.get("tools") or {}) if isinstance(cfg, dict) else {}
    include_deferred_rdkit_agent = coerce_bool(
        tools_cfg.get("rdkit_agent_deferred"),
        env="OPENMOLCLAW_TOOLS_RDKIT_AGENT_DEFERRED",
        default=True,
    )
    registry = build_default_registry(
        include_deferred_rdkit_agent=include_deferred_rdkit_agent
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_app_endpoints.py tests/test_app_chat.py -v`
Expected: all PASS.

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS, no regressions.

- [ ] **Step 6: Commit**

```bash
git add src/openmolclaw/app.py tests/test_app_endpoints.py tests/test_app_chat.py
git commit -m "feat: gate deferred rdkit-agent tools behind tools.rdkit_agent_deferred config"
```

---

### Task 3: Frontend workflow form (index.html + app.js)

**Files:**
- Modify: `src/openmolclaw/web/index.html:78-89` (insert new form before the "Rendered preview" heading)
- Modify: `src/openmolclaw/web/app.js` (append new event wiring near the end, before the `window.addEventListener("load", ...)` block at line 258)
- Modify: `src/openmolclaw/web/style.css` (append rules for the new form)
- Test: append one Flask-test-client markup assertion to `tests/test_app_endpoints.py`

**Interfaces:**
- Consumes: existing `#chat-input` / `#chat-form` DOM nodes owned by `chat.js` (shared via plain DOM ids, not a JS export — matches the existing `app.js`/`chat.js` split, both plain IIFEs with no shared module boundary).
- Produces: DOM ids `rdkit-agent-form`, `rdkit-agent-workflow`, `rdkit-agent-input` for Task 4 (none needed) and for manual QA.

- [ ] **Step 1: Write the failing markup test**

Append to `tests/test_app_endpoints.py`:

```python
def test_index_html_includes_rdkit_agent_workflow_form(client):
    r = client.get("/")
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert 'id="rdkit-agent-form"' in html
    assert 'id="rdkit-agent-workflow"' in html
    assert 'id="rdkit-agent-input"' in html
    assert "rdkit-agent" in html  # link text / repo reference present
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_app_endpoints.py::test_index_html_includes_rdkit_agent_workflow_form -v`
Expected: FAIL — markup not present yet.

- [ ] **Step 3: Insert the form markup in `index.html`**

In `src/openmolclaw/web/index.html`, insert immediately before the `<h3>Rendered preview</h3>` line (currently line 87), i.e. between the status `<div class="tool-row">` block and the preview heading:

```html
      <form id="rdkit-agent-form" class="tool-row rdkit-agent-tools">
        <h3>Optional rdkit-agent workflows</h3>
        <p class="small-note">
          These actions ask the AI to prepare an rdkit-agent tool call through
          the chat panel above. OpenMolClaw does not execute the CLI. See
          <a href="https://github.com/scottmreed/rdkit-agent" target="_blank" rel="noopener noreferrer">rdkit-agent on GitHub</a>.
        </p>
        <label for="rdkit-agent-workflow">Workflow</label>
        <select id="rdkit-agent-workflow" name="workflow">
          <option value="similarity">Similarity search</option>
          <option value="atom-map">Atom mapping</option>
          <option value="balance">Reaction balance check</option>
          <option value="fingerprint">Fingerprint generation</option>
        </select>
        <label for="rdkit-agent-input">Input</label>
        <textarea id="rdkit-agent-input" name="input" rows="3"
          placeholder="Enter SMILES, reaction notation, or a molecule list"></textarea>
        <button type="submit">Ask AI to prepare rdkit-agent call</button>
      </form>

```

- [ ] **Step 4: Run it to verify it passes**

Run: `pytest tests/test_app_endpoints.py::test_index_html_includes_rdkit_agent_workflow_form -v`
Expected: PASS.

- [ ] **Step 5: Add the JS prompt builder + submit handler in `app.js`**

Append this block to `src/openmolclaw/web/app.js`, immediately before the closing `window.addEventListener("load", () => {` block (currently starting at line 258):

```javascript
// --- optional rdkit-agent deferred workflows -------------------------------
//
// These do not call /api/execute directly. They build a chat prompt naming
// the matching rdkit_agent_* tool and submit it through the normal chat form,
// so the LLM (not this script) decides whether/how to call the tool. See
// docs/rdkit_agent_deferred_tools.md.
function rdkitAgentPrompt(workflow, input) {
  const prompts = {
    similarity:
      `Use the rdkit_agent_similarity_search tool to prepare a deferred rdkit-agent similarity search.\n` +
      `Input:\n${input}\n` +
      `Return the prepared external rdkit-agent invocation and explain how to run it outside OpenMolClaw.`,
    "atom-map":
      `Use the rdkit_agent_atom_map tool to prepare a deferred rdkit-agent atom-map operation.\n` +
      `Input:\n${input}\n` +
      `Return the prepared external rdkit-agent invocation and explain what the result would be used for.`,
    balance:
      `Use the rdkit_agent_reaction_balance_check tool to prepare a deferred rdkit-agent reaction balance check.\n` +
      `Input:\n${input}\n` +
      `Return the prepared external rdkit-agent invocation and explain what balance issues the external tool should detect.`,
    fingerprint:
      `Use the rdkit_agent_fingerprint tool to prepare a deferred rdkit-agent fingerprint request.\n` +
      `Input:\n${input}\n` +
      `Return the prepared external rdkit-agent invocation and explain how fingerprints can be used downstream.`,
  };
  return prompts[workflow] || input;
}

const rdkitAgentForm = $("rdkit-agent-form");
if (rdkitAgentForm) {
  rdkitAgentForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const workflow = $("rdkit-agent-workflow").value;
    const input = $("rdkit-agent-input").value.trim();
    if (!input) {
      setStatus("Enter input for the rdkit-agent workflow.", true);
      return;
    }
    const chatInput = document.getElementById("chat-input");
    const chatForm = document.getElementById("chat-form");
    if (!chatInput || !chatForm) {
      setStatus("Chat panel is not available.", true);
      return;
    }
    chatInput.value = rdkitAgentPrompt(workflow, input);
    chatForm.requestSubmit();
    setStatus(`Asked the AI to prepare a ${workflow} request.`);
  });
}
```

- [ ] **Step 6: Add CSS for the new form**

Append to `src/openmolclaw/web/style.css`:

```css
/* --- Optional rdkit-agent deferred workflows ----------------------------- */
.rdkit-agent-tools textarea {
  width: 100%;
  padding: 0.5rem 0.6rem;
  border: 1px solid var(--line);
  border-radius: 6px;
  font: inherit;
  resize: vertical;
  min-height: 3.5rem;
}
.rdkit-agent-tools select { width: 100%; margin-bottom: 0.5rem; }
.rdkit-agent-tools button { margin-top: 0.4rem; }
```

- [ ] **Step 7: Manual smoke check (no JS test runner in this repo)**

Run: `python -m openmolclaw serve &` then `curl -s http://127.0.0.1:5000/ | grep rdkit-agent-form`
Expected: the form tag is present in the served HTML. Stop the server afterward (`kill %1` or `pkill -f "openmolclaw serve"`).

- [ ] **Step 8: Commit**

```bash
git add src/openmolclaw/web/index.html src/openmolclaw/web/app.js src/openmolclaw/web/style.css tests/test_app_endpoints.py
git commit -m "feat: add rdkit-agent workflow form that routes through chat tool-calling"
```

---

### Task 4: Render deferred tool results as chat cards

**Files:**
- Modify: `src/openmolclaw/web/chat.js:82-104` (add a sibling render function; call it from `sendMessage`)
- Modify: `src/openmolclaw/web/style.css` (append card styles)

**Interfaces:**
- Consumes: `data.steps[].result` shape produced by Task 1's `_deferred()` envelope (`execution_status`, `external_command`, `recommended_cli`, `provider_repo`, `notes`) — already present in every `/api/chat` response step, no API change needed.
- Produces: nothing consumed elsewhere; purely additive rendering.

- [ ] **Step 1: Add the card renderer in `chat.js`**

In `src/openmolclaw/web/chat.js`, add this function immediately after `addStructures` (after line 104, before `async function loadIntoEditor`):

```javascript
  // Render deferred rdkit-agent tool results (execution_status ===
  // "deferred_external_tool") as an explicit card so the user can see
  // OpenMolClaw prepared, but did not run, the external command.
  function addDeferredCards(steps) {
    if (!steps || !steps.length) return;
    steps
      .filter((s) => s.ok && s.result && s.result.execution_status === "deferred_external_tool")
      .forEach((s) => {
        const r = s.result;
        const card = el("div", "chat-deferred-card");
        card.appendChild(
          el("div", "chat-deferred-head", `Deferred rdkit-agent request: ${r.external_command}`)
        );
        const cli = el("pre", "chat-deferred-cli", r.recommended_cli);
        card.appendChild(cli);
        if (r.provider_repo) {
          const link = document.createElement("a");
          link.href = r.provider_repo;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = "rdkit-agent on GitHub";
          card.appendChild(link);
        }
        if (Array.isArray(r.notes) && r.notes.length) {
          card.appendChild(el("p", "chat-deferred-notes", r.notes.join(" ")));
        }
        log.appendChild(card);
      });
    log.scrollTop = log.scrollHeight;
  }
```

Then update `sendMessage` (currently `src/openmolclaw/web/chat.js:147-149`) to call it:

```javascript
      if (data.ok) {
        addTrace(data.steps);
        addDeferredCards(data.steps);
        addStructures(data.workspace);
```

- [ ] **Step 2: Add CSS for the card**

Append to `src/openmolclaw/web/style.css`:

```css
.chat-deferred-card {
  margin: 0.4rem 0;
  padding: 0.5rem 0.7rem;
  border: 1px solid var(--accent);
  border-radius: 6px;
  background: #f2f9fb;
}
.chat-deferred-head { font-weight: 700; margin-bottom: 0.3rem; }
.chat-deferred-cli {
  background: rgba(15, 109, 132, 0.08);
  padding: 0.4rem 0.5rem;
  border-radius: 4px;
  overflow-x: auto;
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  font-size: 0.85rem;
  margin: 0.3rem 0;
}
.chat-deferred-notes { color: var(--ink-soft); font-size: 0.82rem; margin: 0.3rem 0 0; }
```

- [ ] **Step 3: Manual smoke check**

Run: `python -m openmolclaw serve` (needs a reachable model provider to actually exercise chat end-to-end; otherwise confirm no console errors by opening the page and checking that `addDeferredCards` is defined: open browser dev tools on `http://127.0.0.1:5000/` and run `typeof addDeferredCards` — expect `"undefined"` from outside the closure is fine, the real check is that the page loads with no JS console errors after the edit).
Run: `pytest -q` (regression guard — no Python changed in this task, but confirms nothing else broke).
Expected: page loads without console errors; `pytest -q` still PASS.

- [ ] **Step 4: Commit**

```bash
git add src/openmolclaw/web/chat.js src/openmolclaw/web/style.css
git commit -m "feat: render deferred rdkit-agent tool results as chat cards"
```

---

### Task 5: Documentation

**Files:**
- Modify: `README.md:40-59` (add a bullet under "What's inside")
- Modify: `docs/chat.md` (add a new "Optional rdkit-agent deferred tools" section after the "Tools the chat can call" table, i.e. after line 47/before line 49)
- Create: `docs/rdkit_agent_deferred_tools.md`

**Interfaces:**
- None — documentation only, no code interfaces.

- [ ] **Step 1: Add the README bullet**

In `README.md`, insert this bullet at the end of the "What's inside" list (after the "Explicit model providers" bullet, currently `README.md:58`):

```markdown
- **Optional rdkit-agent deferred tools**: OpenMolClaw can advertise selected
  [`rdkit-agent`](https://github.com/scottmreed/rdkit-agent) workflows to the
  LLM as standard tool-call options, including similarity search, atom mapping,
  reaction balance checks, and fingerprints. OpenMolClaw does not execute the
  CLI directly; it prepares structured external invocation payloads for agents
  or runtimes that have `rdkit-agent` installed. Enabled by default; disable
  with `tools.rdkit_agent_deferred: false` in config.
```

- [ ] **Step 2: Add the `docs/chat.md` section**

In `docs/chat.md`, insert this new section right after the "Tools the chat can call" table and before the "## Using it" heading (currently between lines 47 and 49):

```markdown
## Optional rdkit-agent deferred tools

OpenMolClaw also exposes four `rdkit_agent_*` tool schemas that prepare
[`rdkit-agent`](https://github.com/scottmreed/rdkit-agent) CLI invocations
without ever running the CLI:

| Tool | Prepares |
|------|----------|
| `rdkit_agent_similarity_search` | a similarity search over target SMILES |
| `rdkit_agent_atom_map` | an atom-map list/add/remove/check operation |
| `rdkit_agent_reaction_balance_check` | a reaction balance check |
| `rdkit_agent_fingerprint` | Morgan/topological fingerprint generation |

Every result carries `execution_status: "deferred_external_tool"` and
`openmolclaw_executed_cli: false`. OpenMolClaw prepares the request only; an
external agent/runtime with `rdkit-agent` installed can run the
`recommended_cli` command shown in the result to actually execute it. These
tools are enabled by default (`tools.rdkit_agent_deferred: true`); set it to
`false` in config, or set `OPENMOLCLAW_TOOLS_RDKIT_AGENT_DEFERRED=0`, to hide
them from `/api/tools` entirely. See
[`rdkit_agent_deferred_tools.md`](rdkit_agent_deferred_tools.md) for the full
payload shape and example calls.
```

- [ ] **Step 3: Create `docs/rdkit_agent_deferred_tools.md`**

```markdown
# Optional rdkit-agent deferred tools

OpenMolClaw can advertise selected
[`rdkit-agent`](https://github.com/scottmreed/rdkit-agent) workflows to the
configured LLM as standard provider-neutral tool-call schemas. This page
describes exactly what the feature is, what it is not, and how to use it.

## What this is

Four tool schemas — `rdkit_agent_similarity_search`, `rdkit_agent_atom_map`,
`rdkit_agent_reaction_balance_check`, `rdkit_agent_fingerprint` — registered
into the same `ToolRegistry` as OpenMolClaw's built-in RDKit tools. When the
chat model selects one, OpenMolClaw runs a small local Python function that
validates the arguments and returns a structured envelope describing the
equivalent `rdkit-agent` CLI invocation.

## What this is not

- OpenMolClaw does **not** shell out to, install, or depend on the
  `rdkit-agent` CLI, `npm`, or `node`. No handler imports `subprocess`.
- The tools do not perform the similarity/fingerprint/balance/atom-map
  computation themselves — they only prepare the request. An external agent or
  runtime with `rdkit-agent` installed must run the returned command to get an
  actual result.
- The chat responder is expected to say the request was "prepared" or
  "deferred," never "computed" or "executed."

## Supported workflows

| Tool | Required arguments | Optional arguments |
|------|--------------------|---------------------|
| `rdkit_agent_similarity_search` | `query_smiles`, `target_smiles` (array) | `threshold` (default `0.5`), `top_n` (default `5`), `fingerprint` (`morgan`\|`topological`, default `morgan`) |
| `rdkit_agent_atom_map` | `operation` (`list`\|`add`\|`remove`\|`check`) | `smiles` (required for `list`/`add`/`remove`), `smirks` (accepted for `check`, along with `smiles`) |
| `rdkit_agent_reaction_balance_check` | either `reaction_smiles`, or both `reactants` and `products` (arrays) | — |
| `rdkit_agent_fingerprint` | `smiles` (array) | `fingerprint` (default `morgan`), `radius` (default `2`), `n_bits` (default `2048`) |

## Example `/api/chat` prompt

```bash
curl -s http://127.0.0.1:5000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Use the rdkit_agent_similarity_search tool to compare CCO against CCN and CCC.", "history": []}'
```

## Example `/api/execute` call

```bash
curl -s http://127.0.0.1:5000/api/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "rdkit_agent_fingerprint", "args": {"smiles": ["CCO"]}}'
```

## Deferred payload shape

Every handler returns:

```json
{
  "execution_status": "deferred_external_tool",
  "tool_provider": "rdkit-agent",
  "provider_repo": "https://github.com/scottmreed/rdkit-agent",
  "openmolclaw_executed_cli": false,
  "external_command": "similarity",
  "recommended_cli": "rdkit-agent similarity --json - --output json",
  "arguments": { "...": "normalized, tool-specific arguments" },
  "notes": [
    "OpenMolClaw prepared this request as a tool-call payload only.",
    "OpenMolClaw did not run the rdkit-agent CLI.",
    "An external agent/runtime with rdkit-agent installed may execute it."
  ]
}
```

## How an external agent executes the payload

Copy the `arguments` object and pipe it to the `recommended_cli` command shown
in the result, e.g.:

```bash
echo '{"query": "CCO", "targets": ["CCN", "CCC"], "threshold": 0.5, "top": 5, "fingerprint": "morgan"}' \
  | rdkit-agent similarity --json - --output json
```

This step happens outside OpenMolClaw, in an environment where the
`rdkit-agent` CLI is installed (see the
[`rdkit-agent` README](https://github.com/scottmreed/rdkit-agent) for install
instructions).

## Configuration

```yaml
tools:
  rdkit_agent_deferred: true   # default; set false to hide these 4 tools
```

Or via environment variable: `OPENMOLCLAW_TOOLS_RDKIT_AGENT_DEFERRED=0`.

## Security notes

- No shell interpolation: arguments are passed as a Python dict / JSON object,
  never concatenated into a command string that OpenMolClaw itself runs.
- Local-preparation-only: these tools are allowed under Private Structure Mode
  (see [`zdr.md`](zdr.md)) — unlike `lookup_compound`, they make no network
  call and disclose nothing beyond what the user typed into the local chat.
- A future, separate PRD may define an opt-in external runner that actually
  invokes `rdkit-agent` on the user's behalf; that is explicitly out of scope
  here and would require its own consent flow, command allowlist, and
  sandboxing.
```

- [ ] **Step 4: Verify links and references**

Run: `grep -rn "rdkit-agent" README.md docs/chat.md docs/rdkit_agent_deferred_tools.md`
Expected: the GitHub link `https://github.com/scottmreed/rdkit-agent` appears in all three files.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/chat.md docs/rdkit_agent_deferred_tools.md
git commit -m "docs: document the optional rdkit-agent deferred tool-calling surface"
```

---

### Task 6: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: all tests PASS, no warnings about missing modules.

- [ ] **Step 2: Run `doctor`**

Run: `python -m openmolclaw doctor`
Expected: exits 0; tool registry check includes the 14 tools (10 existing + 4 new).

- [ ] **Step 3: Confirm no CLI/subprocess dependency was introduced**

Run: `grep -rn "subprocess\|rdkit-agent\b" src/openmolclaw/*.py pyproject.toml | grep -v "rdkit_agent_tools.py\|# \|docs/"`

Expected: no matches beyond the doc-string/URL references already reviewed in Task 1 and Task 5 (i.e., no executable `subprocess` call anywhere in `src/openmolclaw`, and no `rdkit-agent`/`npm`/`node` dependency line in `pyproject.toml`).

- [ ] **Step 4: Manual browser QA (per PRD §13 — not automatable with pytest)**

Run `python -m openmolclaw serve`, open `http://127.0.0.1:5000/`, and manually:
1. Confirm the "Optional rdkit-agent workflows" section renders in the Tools panel.
2. Pick each of the 4 workflows, enter sample input (e.g. `CCO` for similarity/fingerprint, `CCO>>CC=O` for balance, `[CH3:1]>>[CH3:1]` for atom-map check), click the button, and confirm it populates and submits the chat form.
3. With a reachable model configured, confirm the assistant's reply and the new deferred-request card render, and that the reply text says "prepared"/"deferred," not "computed"/"executed."
4. Confirm no CLI install was required for any of this.
