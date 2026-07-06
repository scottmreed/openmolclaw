# API contracts

The stable public surface of OpenMolClaw: the HTTP routes, the tool contracts,
the error envelope, and the contract suite that guards them. All of it works
offline; only the model-calling and PubChem-lookup paths touch the network.

## HTTP routes (Flask app factory)

Build the app with `openmolclaw.app.create_app()` or run `openmolclaw serve`.

| Method | Route | Purpose |
|---|---|---|
| GET | `/` | Local Ketcher UI (or a JSON stub if the bundle is absent). |
| GET | `/web/<path>` | Static UI assets. |
| GET | `/docs` | Minimal HTML API documentation. |
| GET | `/api/health` | `{ok, version, provider, tools}`. |
| GET | `/api/docs` | Machine-readable `{version, attribution, provider, routes, tools}`. |
| GET | `/api/tools` | `{tools: [<schema>, ...]}` — the stable tool contracts. |
| POST | `/api/tools/<name>` | Run one tool; body is the tool args. Returns the result envelope. |
| POST | `/api/execute` | Run a tool by `{"tool": name, "args": {...}}`. |
| GET | `/api/contracts` | Run the in-package contract suite; `200` if all pass, else `500`. |
| POST | `/api/validate` | RDKit SMILES validation. |
| POST | `/api/render` | Render a molecule (SMILES) to SVG and add it to the workspace. |
| POST | `/api/smiles-to-molblock` | SMILES → Molblock (for loading into Ketcher). |
| POST | `/api/molblock-to-smiles` | Read the current Ketcher structure back to SMILES. |
| GET/POST | `/api/workspace` | Inspect / append to the local workspace. |

## Tool contracts

`GET /api/tools` (and `openmolclaw list-tools --json`) return provider-neutral
function-calling schemas. The built-in set is stable:

| Tool | Args | Returns |
|---|---|---|
| `validate_smiles` | `{smiles}` | `{valid, detail}` |
| `render_molecule` | `{smiles, width?, height?}` | `{format: "svg", svg}` |
| `convert_smiles` | `{smiles}` | `{sanitized_smiles, valid, detail}` |
| `lookup_compound` | `{name}` | `{name, smiles}` (PubChem; network) |

Each schema has the shape:

```json
{
  "type": "function",
  "function": {
    "name": "validate_smiles",
    "description": "...",
    "parameters": {"type": "object", "properties": {"smiles": {"type": "string"}}, "required": ["smiles"]}
  }
}
```

## Error envelope

Tool execution (`/api/execute`, `/api/tools/<name>`, and the `ToolExecutor`)
normalizes every failure into a stable envelope — never a raw traceback:

```json
{"ok": false, "tool_name": "...", "result": null, "error": "...", "error_type": "...", "duration_ms": 0.0}
```

| `error_type` | Meaning | HTTP status |
|---|---|---|
| `unknown_tool` | No such tool in the registry. | 404 |
| `gate_denied` | A `ToolGate` refused the call. | 403 |
| `bad_arguments` | Missing/invalid arguments for the handler. | 400 |
| `tool_error` | The handler raised. | 400 |

Successful calls return `{"ok": true, "result": <value>, ...}` with status `200`.

## Contract suite

The in-package suite (`openmolclaw.contracts.run_contracts()`, the
`run-contracts` CLI, and `GET /api/contracts`) exercises the public API surface
deterministically and offline. Areas:

- **name_resolution** — PubChem name→SMILES via an injected transport (no network).
- **smiles** — validation, conversion/sanitization, canonicalization determinism.
- **tool_schemas** — the tool set and schema shape are stable.
- **error_envelopes** — every executor failure mode normalizes correctly.
- **provider_policy** — fail-closed selection; no silent commercial fallback;
  OpenRouter endpoint/tool-support checks.
- **response_envelopes** — router JSON parsing + `RouterDecision` validation.

A separate parity suite in [`tests/contract/`](../tests/contract/) proves the
public package and the private ChemIllusion `agent_core` produce byte-identical
outputs for shared fixtures (PRD §12.3).

## Environment variables

See [`model_providers.md`](model_providers.md#environment-variables). None are
required for install, `doctor`, `list-tools`, `run-contracts`, or the test suite.
