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
