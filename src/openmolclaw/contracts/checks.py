"""In-package contract checks (OpenMolClaw).

Each check exercises one part of the **public API surface** and raises
``AssertionError`` (or a specific exception) on divergence. The
:mod:`openmolclaw.contracts` runner wraps them so both ``openmolclaw
run-contracts`` (CLI) and ``pytest`` report the same results.

Everything here is deterministic and runs **without network access or secrets**:

* name/molecule resolution uses a canned PubChem transport,
* SMILES validation/conversion + canonicalization use local RDKit,
* tool schemas, error envelopes, and provider fail-closed behavior use only
  in-process objects (the fail-closed provider checks assert that misconfigured
  providers *raise* — they never make a network call).

This complements the cross-repo parity suite in ``tests/contract/`` (which
proves public/private byte-identical outputs); these checks prove the *public
package's own* contracts hold from an installed wheel.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any, Callable, Dict, List, Tuple

from ..builtin_tools import build_default_registry
from ..chemistry import convert, lookup, validate
from ..chemistry.rdkit_tools import SMILESUtilities
from ..config import UnknownProvider, build_provider
from ..harness.defaults import AllowAllToolGate
from ..harness.executor import ToolExecutor
from ..harness.interfaces import GateResult, ToolContext
from ..harness.providers.openrouter import (
    OpenRouterProvider,
    ProviderEndpointError,
    evaluate_openrouter_model,
)
from ..harness.router import Router, parse_router_json_content
from ..harness.schemas import RouterDecision
from ..harness.tool_registry import ToolRegistry

# A single check: (area, name, callable-that-raises-on-failure).
Check = Tuple[str, str, Callable[[], None]]


def _load_json_resource(filename: str) -> Dict[str, Any]:
    data = resources.files("openmolclaw.contracts.data").joinpath(filename).read_text(
        encoding="utf-8"
    )
    return json.loads(data)


# ---------------------------------------------------------------------------
# 1. molecule / name resolution (offline, canned PubChem transport)
# ---------------------------------------------------------------------------


def _canned_pubchem_fetch(payload: Dict[str, Any]) -> lookup.Fetcher:
    def fetch(url: str, timeout: float) -> lookup.FetchResult:  # noqa: ARG001
        if "IsomericSMILES" in url or "CanonicalSMILES" in url:
            return lookup.FetchResult(status_code=200, json=payload)
        return lookup.FetchResult(status_code=404, json=None)

    return fetch


def check_name_resolution_hit() -> None:
    payload = _load_json_resource("pubchem_ethanol.json")
    got = lookup.name_to_smiles("ethanol", fetch=_canned_pubchem_fetch(payload))
    assert got == "CCO", f"expected CCO, got {got!r}"


def check_name_resolution_miss() -> None:
    def not_found(url: str, timeout: float) -> lookup.FetchResult:  # noqa: ARG001
        return lookup.FetchResult(status_code=404, json=None)

    got = lookup.name_to_smiles_or_none("definitely-not-a-compound", fetch=not_found)
    assert got is None, f"expected None for a miss, got {got!r}"


# ---------------------------------------------------------------------------
# 2. SMILES validation / conversion (local RDKit, deterministic)
# ---------------------------------------------------------------------------


def check_smiles_validation() -> None:
    ok, cleaned = validate.validate_smiles_string("CCO")
    assert ok and cleaned == "CCO", (ok, cleaned)

    bad, _ = validate.validate_smiles_string("this is the molecule")
    assert bad is False, "prose-corrupted SMILES must be rejected"

    broken, _ = validate.validate_smiles_string("C1CCCCC")  # unclosed ring
    assert broken is False, "RDKit-unparseable SMILES must be rejected"


def check_smiles_conversion() -> None:
    assert convert.sanitize_smiles("  CCO \n") == "CCO"
    is_valid, _ = convert.validate_smiles("benzophenone")
    assert is_valid is False, "a bare name must not validate as SMILES"


def check_canonicalization_determinism() -> None:
    # Two equivalent inputs canonicalize to the same string.
    a = SMILESUtilities.canonicalize_smiles("OCC")
    b = SMILESUtilities.canonicalize_smiles("C(O)C")
    assert a == b == "CCO", (a, b)


# ---------------------------------------------------------------------------
# 3. tool schemas (stable public tool contracts)
# ---------------------------------------------------------------------------

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


def check_tool_schema_shape() -> None:
    specs = build_default_registry().specs()
    names = {s["function"]["name"] for s in specs}
    assert names == _EXPECTED_TOOLS, f"tool set drifted: {sorted(names)}"
    for spec in specs:
        assert spec.get("type") == "function", spec
        fn = spec["function"]
        assert isinstance(fn.get("name"), str) and fn["name"], spec
        assert isinstance(fn.get("description"), str), spec
        params = fn.get("parameters") or {}
        assert params.get("type") == "object", spec
        assert isinstance(params.get("properties"), dict), spec


# ---------------------------------------------------------------------------
# 4. error envelopes (executor normalizes every failure mode)
# ---------------------------------------------------------------------------


def _tiny_registry() -> ToolRegistry:
    reg = ToolRegistry()

    def needs_x(x: int) -> Dict[str, Any]:
        return {"x": x}

    def boom() -> None:
        raise RuntimeError("kaboom")

    reg.register(
        "needs_x",
        needs_x,
        description="needs x",
        parameters={"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]},
    )
    reg.register("boom", boom, description="always raises", parameters={"type": "object", "properties": {}})
    return reg


class _DenyGate:
    def check(self, tool_name: str, context: ToolContext) -> GateResult:  # noqa: ARG002
        return GateResult.deny("denied by contract test")


def check_error_envelope_unknown_tool() -> None:
    ex = ToolExecutor(_tiny_registry(), tool_gate=AllowAllToolGate())
    r = ex.execute("nope", {})
    assert r.ok is False and r.error_type == "unknown_tool", r.as_trace()


def check_error_envelope_bad_arguments() -> None:
    ex = ToolExecutor(_tiny_registry(), tool_gate=AllowAllToolGate())
    r = ex.execute("needs_x", {})  # missing required kw
    assert r.ok is False and r.error_type == "bad_arguments", r.as_trace()


def check_error_envelope_tool_error() -> None:
    import logging

    ex = ToolExecutor(_tiny_registry(), tool_gate=AllowAllToolGate())
    exec_log = logging.getLogger("openmolclaw.harness.executor")
    prev = exec_log.level
    exec_log.setLevel(logging.CRITICAL)  # the raise is intentional; don't log its traceback
    try:
        r = ex.execute("boom", {})
    finally:
        exec_log.setLevel(prev)
    assert r.ok is False and r.error_type == "tool_error", r.as_trace()


def check_error_envelope_gate_denied() -> None:
    ex = ToolExecutor(_tiny_registry(), tool_gate=_DenyGate())
    r = ex.execute("needs_x", {"x": 1})
    assert r.ok is False and r.error_type == "gate_denied", r.as_trace()


# ---------------------------------------------------------------------------
# 5. provider fail-closed behavior (no silent OpenAI fallback)
# ---------------------------------------------------------------------------


def check_provider_default_is_local_bundled() -> None:
    # The built-in default builds a bundled local provider — never a commercial one.
    provider = build_provider()  # default config
    assert type(provider).__name__ == "LocalProvider", type(provider).__name__


def check_provider_openai_requires_endpoint() -> None:
    try:
        build_provider({"model": {"provider": "openai", "model": "gpt"}})
    except UnknownProvider:
        return
    raise AssertionError("selecting 'openai' without endpoint must fail closed")


def check_provider_named_endpoint_is_explicit() -> None:
    provider = build_provider(
        {
            "model": {
                "provider": "claude",
                "model": "x",
                "endpoint": "https://example.test/v1",
            }
        }
    )
    assert type(provider).__name__ == "LocalProvider", type(provider).__name__


def check_provider_unknown_errors() -> None:
    try:
        build_provider({"model": {"provider": "totally-made-up"}})
    except UnknownProvider:
        return
    raise AssertionError("an unknown provider must raise UnknownProvider")


def check_openrouter_requires_key() -> None:
    provider = OpenRouterProvider(model="google/gemma-4-26b-a4b-it", api_key="")
    try:
        provider.complete_with_tools(messages=[{"role": "user", "content": "hi"}], tools=[])
    except RuntimeError:
        return
    raise AssertionError("OpenRouter with no key must fail closed, not call anything")


def check_openrouter_no_endpoint_fails_closed() -> None:
    try:
        evaluate_openrouter_model("missing/model", [])
    except ProviderEndpointError:
        return
    raise AssertionError("an absent model must raise ProviderEndpointError")


def check_openrouter_no_tool_support_fails_closed() -> None:
    records = [{"id": "vendor/model", "supported_parameters": ["temperature"]}]
    try:
        evaluate_openrouter_model("vendor/model", records, require_tools=True)
    except ProviderEndpointError:
        return
    raise AssertionError("a model lacking tool support must raise ProviderEndpointError")


def check_openrouter_tool_support_ok() -> None:
    records = [{"id": "vendor/model", "supported_parameters": ["tools", "temperature"]}]
    assert evaluate_openrouter_model("vendor/model", records, require_tools=True) is True


# ---------------------------------------------------------------------------
# 6. response envelopes (router decision parse + schema validation)
# ---------------------------------------------------------------------------


def check_router_parse_fenced_and_duplicated() -> None:
    content = '```json\n{"intent":"action","tool_name":"validate_smiles","tool_args":{"smiles":"CCO"}}\n```'
    payload = parse_router_json_content(content)
    decision = Router.decision_from_payload(payload)
    assert decision.tool_name == "validate_smiles"
    assert decision.tool_args == {"smiles": "CCO"}
    assert decision.conversational is False


def check_router_decision_schema_defaults() -> None:
    d = RouterDecision(intent="question", tool_name="")
    assert d.conversational is False and d.confidence == 0.0
    dumped = d.model_dump()
    assert dumped["tool_name"] == "" and dumped["intent"] == "question"


# ---------------------------------------------------------------------------
# Registry of all checks, grouped by contract area.
# ---------------------------------------------------------------------------

CHECKS: List[Check] = [
    ("name_resolution", "resolves_known_name", check_name_resolution_hit),
    ("name_resolution", "misses_gracefully", check_name_resolution_miss),
    ("smiles", "validation", check_smiles_validation),
    ("smiles", "conversion", check_smiles_conversion),
    ("smiles", "canonicalization_deterministic", check_canonicalization_determinism),
    ("tool_schemas", "shape_and_names", check_tool_schema_shape),
    ("error_envelopes", "unknown_tool", check_error_envelope_unknown_tool),
    ("error_envelopes", "bad_arguments", check_error_envelope_bad_arguments),
    ("error_envelopes", "tool_error", check_error_envelope_tool_error),
    ("error_envelopes", "gate_denied", check_error_envelope_gate_denied),
    ("provider_policy", "default_is_local_bundled", check_provider_default_is_local_bundled),
    ("provider_policy", "openai_requires_endpoint", check_provider_openai_requires_endpoint),
    ("provider_policy", "named_endpoint_is_explicit", check_provider_named_endpoint_is_explicit),
    ("provider_policy", "unknown_provider_errors", check_provider_unknown_errors),
    ("provider_policy", "openrouter_requires_key", check_openrouter_requires_key),
    ("provider_policy", "openrouter_no_endpoint", check_openrouter_no_endpoint_fails_closed),
    ("provider_policy", "openrouter_no_tool_support", check_openrouter_no_tool_support_fails_closed),
    ("provider_policy", "openrouter_tool_support_ok", check_openrouter_tool_support_ok),
    ("response_envelopes", "router_parse", check_router_parse_fenced_and_duplicated),
    ("response_envelopes", "router_schema_defaults", check_router_decision_schema_defaults),
]


__all__ = ["Check", "CHECKS"]
