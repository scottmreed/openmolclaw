# Chat

OpenMolClaw ships a conversational chat loop so you can ask for chemistry in
plain language instead of calling tools by hand. Ask a question, and the
harness routes it to the right local RDKit tool, runs it, and writes the reply
with the model **you** configured — locally or through an OpenRouter ZDR
endpoint. No structures are sent to a ChemIllusion server.

## How a turn works

```
user message
   │
   ▼
Router  ──(model call #1)──▶  picks at most one tool + its arguments
   │
   ▼
ToolExecutor  ──▶  runs the tool (gated, traced) and returns a result
   │                (optionally loops, bounded by max_tool_steps, so the
   │                 model can chain a couple of steps — it stops on a
   │                 conversational decision, a tool error, a repeated
   │                 (tool, args), or the step cap)
   ▼
Responder  ──(model call #2)──▶  writes the natural-language reply, grounded
                                  only in what the tools actually returned
```

The loop is provider-neutral (`openmolclaw.harness.chat.run_chat_turn`) and
carries no plan, quota, vendor, or storage coupling — the local Flask app wraps
it and layers workspace persistence on top.

## Tools the chat can call

All are deterministic, local, 2D-graph cheminformatics:

| Tool | What it does |
|------|--------------|
| `validate_smiles` | RDKit validity check |
| `canonicalize_smiles` | canonical SMILES |
| `convert_smiles` | sanitize + validate |
| `molecular_descriptors` | formula, MW, exact mass, logP, TPSA, H-bond donors/acceptors, rotatable bonds, ring counts, heavy atoms, charge |
| `substructure_search` | SMARTS (or SMILES) match + matching atom indices |
| `functional_groups` | common functional groups present |
| `stereochemistry` | chiral centers (R/S) + E/Z stereo bond count |
| `to_inchi` | standard InChI + InChIKey |
| `render_molecule` | 2D SVG |
| `lookup_compound` | name → SMILES (PubChem; blocked under Private Structure Mode) |

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

## Using it

### In the browser

Run `python -m openmolclaw serve` and open the local URL. Pick a model in the
**Tools** panel, then type in the **Chat** panel. Structures the tools produce
render inline and can be loaded straight into the Ketcher editor.

### Over HTTP

```bash
curl -s http://127.0.0.1:5000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "What functional groups are in aspirin, CC(=O)Oc1ccccc1C(=O)O?", "history": []}'
```

Response shape:

```json
{
  "ok": true,
  "reply": "Aspirin contains an ester and a carboxylic acid…",
  "intent": "action",
  "conversational": false,
  "steps": [{"tool_name": "functional_groups", "args": {"smiles": "…"}, "ok": true, "result": {"functional_groups": ["ester", "carboxylic_acid", "aromatic_ring"]}}],
  "trace": [ … ],
  "workspace": [ … ],
  "messages": [ … ]
}
```

The client holds the conversation `history` and passes it back each turn, so a
stateless server keeps nothing between calls — a memory-only session leaves no
chat history on disk.

## Configuring the model

Chat uses whatever provider your config selects (see
[`model_providers.md`](model_providers.md)). A fully local endpoint needs no
API key:

```yaml
model:
  provider: local
  model: olmo
  endpoint: http://localhost:11434/v1
```

If no model is reachable, `/api/chat` returns a stable `ok:false` envelope with
a user-facing `reply` explaining what to fix — never a 500. Provider selection
is always explicit and fail-closed: OpenMolClaw never guesses an endpoint.

## Privacy

`/api/chat` honors the same posture as the rest of the app
([`zdr.md`](zdr.md)): Private Structure Mode forces a memory-only workspace,
blocks external molecule lookups (the `lookup_compound` tool is denied by the
host gate), and requires ZDR routing when a hosted provider is used. Logs are
run through the structure-redacting filter, so a raw structure never lands in a
log line.
