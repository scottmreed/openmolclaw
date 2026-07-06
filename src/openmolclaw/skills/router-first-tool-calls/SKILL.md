---
name: router-first-tool-calls
description: 'The router-first agent pattern: user request → router → forced tool
  choice → executor → tool result, with JSON-schema validation, an execution trace,
  and deterministic fallback errors. Use when building or reasoning about the local
  agent harness loop so model text is never executed directly.'
---
<!--
SYNCED FILE: Generated from the private ChemIllusion repo.
Source key: router-first-tool-calls
Do not edit directly unless submitting a patch proposal.
Public edits may be overwritten by the next export.
-->

# Router-First Tool Calls

The local harness never executes arbitrary model text. Every agent turn goes
through a **two-step, router-first loop**: the model chooses a tool under a
forced-choice schema, the harness validates the arguments, and a deterministic
executor runs the tool. The model proposes; the harness disposes.

## The loop

```text
user request
    │
    ▼
[ router ]  ── forced tool choice ──►  { "tool": "...", "arguments": { ... } }
    │                                          │
    │                                   JSON-schema validation
    ▼                                          ▼
[ executor ] ── dispatch ──► tool fn ──► tool result ──► trace entry
    │
    ▼
(loop until the router selects `finish`, or a step budget is hit)
```

1. **Router step.** The configured model provider is called with the tool
   schemas and a *forced* tool choice, so it must return a structured tool call —
   not free text.
2. **Validation.** The proposed arguments are validated against the tool's JSON
   schema before anything runs. Invalid arguments produce a deterministic error,
   not an execution.
3. **Executor step.** A plain dispatch table maps the tool name to a Python
   function. The function runs, returns a structured result, and the harness
   appends a trace entry.
4. **Repeat.** The result is fed back for the next router step until the router
   chooses a terminal `finish` tool or the step budget is exhausted.

## Router contract

The router must return JSON of this shape (validate it, never `eval` it):

```json
{
  "tool": "validate_smiles",
  "arguments": { "smiles": "c1ccccc1" }
}
```

Parse defensively — models sometimes wrap JSON in prose or code fences:

```python
import json, re

def parse_router_json(content: str) -> dict:
    # strip ```json ... ``` fences if present
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL)
    raw = m.group(1) if m else content
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("router returned no JSON object")
    return json.loads(raw[start : end + 1])
```

## Forced tool choice via the provider interface

The router depends only on the `ModelProvider` interface, so it works with any
configured local or OpenRouter-compatible model:

```python
class ModelProvider:
    def complete_with_tools(self, messages, tools, tool_choice):
        ...

decision = provider.complete_with_tools(
    messages=history,
    tools=tool_schemas,          # JSON-schema tool definitions
    tool_choice="required",      # force a tool call, not free text
)
```

## Schema validation before dispatch

```python
from jsonschema import validate, ValidationError

def validate_args(tool_name, arguments, registry):
    schema = registry[tool_name]["parameters"]
    try:
        validate(instance=arguments, schema=schema)
    except ValidationError as exc:
        return f"invalid arguments for {tool_name}: {exc.message}"
    return None  # ok
```

## Deterministic executor + trace

```python
def execute(tool_name, arguments, registry, trace):
    err = validate_args(tool_name, arguments, registry)
    if err:
        trace.append({"tool": tool_name, "status": "rejected", "error": err})
        return {"ok": False, "error": err}
    try:
        result = registry[tool_name]["fn"](**arguments)
        trace.append({"tool": tool_name, "status": "ok"})
        return {"ok": True, "result": result}
    except Exception as exc:                    # normalize, never crash the loop
        trace.append({"tool": tool_name, "status": "error", "error": str(exc)})
        return {"ok": False, "error": str(exc)}
```

## Why router-first

- **Safety.** Model text is never executed. Only allowlisted tools run, and only
  with schema-valid arguments.
- **Determinism.** The same tool + arguments always produce the same result;
  fallbacks are explicit error objects, not silent failures.
- **Traceability.** Every step is recorded, so a run is fully inspectable.
- **Portability.** The loop depends only on the `ModelProvider` interface, so
  swapping a local model for an OpenRouter-compatible one changes only config.

---
*Maintained by the [ChemIllusion](https://chemillusion.com) team as part of OpenMolClaw.*
