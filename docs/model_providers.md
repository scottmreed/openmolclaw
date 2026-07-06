# Model providers

OpenMolClaw talks to a **configured model provider** through one small
interface. Provider selection is always an **explicit configuration choice**:
there is no guessed vendor endpoint, no hidden provider switch, and nothing ever
silently falls back to OpenAI or any other model.

## Interface

```python
class ModelProvider:
    def complete_with_tools(self, messages, tools, tool_choice):
        ...
```

Any object implementing this is a provider. The harness (`Router`, `ToolExecutor`)
depends only on this interface, never on a concrete vendor.

## Recommended hosted path: OpenRouter ZDR

The recommended hosted path is OpenRouter with **ZDR Mode** enabled. The legacy
`zdr: true` shorthand still works, but the full privacy block is preferred
because it also denies provider data collection and disables provider fallbacks:

```yaml
model:
  provider: openrouter
  model: google/gemma-4-26b-a4b-it
  base_url: https://openrouter.ai/api/v1
  privacy:
    openrouter_zdr: true        # require Zero Data Retention endpoints
    deny_data_collection: true  # avoid providers that may store data
    allow_fallbacks: false      # never silently route to a backup provider
    require_parameters: true    # only route to endpoints that support the tools
```

Set the key in your environment — never in the file:

```bash
export OPENROUTER_API_KEY=...
```

ZDR Mode makes every OpenRouter request carry a `provider` routing object of
`{"zdr": true, "data_collection": "deny", "allow_fallbacks": false,
"require_parameters": true}`. This is a retention/training control, not
invisibility: the endpoint still processes your request to generate a response,
but supported ZDR endpoints should not retain prompts or use them for training.
ZDR routing is opt-in (off by default) because it can reduce model availability;
see **[docs/zdr.md](zdr.md)** for exactly what it does and does not cover, the
environment-variable overrides, and how to disable local workspace disk
persistence (`workspace.save_mode: memory_only`).

Current tool-capable ZDR model options used by the local Flask selector:

| Model | Notes |
|---|---|
| `google/gemma-4-26b-a4b-it` | Recommended default ZDR option. |
| `amazon/nova-lite-v1` | Lower-cost ZDR option. |
| `deepseek/deepseek-v3.2-exp` | ZDR, tool-capable. |
| `qwen/qwen3-32b` | ZDR, tool-capable. |
| `meta-llama/llama-3.3-70b-instruct` | ZDR, tool-capable. |
| `anthropic/claude-sonnet-4.5` | ZDR through OpenRouter routing when available. |
| `openai/gpt-oss-20b` | ZDR through OpenRouter routing when available. |

## Other explicit providers

### Local model

```yaml
model:
  provider: local
  model: olmo
  endpoint: http://localhost:11434/v1
```

Any local runtime that serves the `/v1/chat/completions` API works. No key is
required by default.

### Any chat-completions-compatible endpoint

```yaml
model:
  provider: openai
  model: gpt-4.1-mini
  endpoint: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY
```

The `provider` value is a label. If it is not `local` or `openrouter`,
OpenMolClaw requires an explicit `endpoint` or `base_url` and sends requests
only there. This is how users can choose OpenAI, Claude-compatible gateways,
Gemini-compatible gateways, lab-hosted models, or any other compatible service
without OpenMolClaw bundling vendor SDKs.

## Provider policy (fail-closed, no silent fallback)

`build_provider(config)` enforces a strict, fail-closed policy:

| `provider:` value | Behavior |
|---|---|
| `local` | **Bundled.** Builds `LocalProvider`. |
| `openrouter` | **Bundled.** Builds `OpenRouterProvider`. |
| any other name with `endpoint` / `base_url` | Builds an explicit chat-completions endpoint provider. |
| any other name without `endpoint` / `base_url` | Raises `UnknownProvider`. |
| *(omitted)* | Defaults to `local` — **never** to a commercial provider. |

Key guarantees:

- **No silent fallback.** A missing or mistyped provider errors; it never quietly
  routes to OpenAI, OpenRouter, a local model, or anything else.
- **Provider names are allowed.** Public docs and configs may name model IDs and
  providers, as long as the chosen endpoint is explicit.

### OpenRouter fail-closed endpoint check

`OpenRouterProvider` refuses to run when it cannot serve tool calls:

- **No API key** → `RuntimeError` (never a no-auth call, never a fallback).
- **Preflight** (opt-in): when enabled, it fetches OpenRouter's model catalog and
  raises `ProviderEndpointError` if the configured model has **no active
  endpoint** or **no endpoint advertising tool-calling** support. The decision
  logic (`evaluate_openrouter_model`) is a pure function, so it is unit-tested
  with no network.

Enable the live preflight per provider or via the environment:

```python
OpenRouterProvider(model="...", preflight=True)
```

```bash
export OPENMOLCLAW_PROVIDER_PREFLIGHT=1
```

Preflight is **off by default** so local contract tests and offline development
never require connectivity.

## Loading a config

```python
from openmolclaw.config import build_provider, load_config
provider = build_provider(load_config("examples/config.local.olmo.yaml"))
```

Or set `OPENMOLCLAW_CONFIG=/path/to/config.yaml` and call `load_config()` with no
argument.

## Environment variables

| Variable | Used by | Purpose |
|---|---|---|
| `OPENMOLCLAW_CONFIG` | `load_config()` | Path to a model config YAML/JSON when none is passed. |
| `OPENROUTER_API_KEY` | `OpenRouterProvider` | Bearer key for OpenRouter. Never committed. |
| `OPENMOLCLAW_PROVIDER_PREFLIGHT` | `OpenRouterProvider` | `1`/`true` enables the live endpoint/tool-support preflight. |

No secrets are required to install the package, run `doctor`, run the contract
suite, or run the offline tests.

## Adding your own provider

Implement `complete_with_tools` and pass your instance to `Router`. A host can
wire any backend (including a commercial one) behind the same interface without
changing harness code — that is exactly the seam the private ChemIllusion
adapters use (PRD §7.3).
