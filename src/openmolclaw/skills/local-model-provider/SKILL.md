---
name: local-model-provider
description: 'Configure OpenMolClaw''s model provider: a local chat-completions
  endpoint, OpenRouter ZDR, or another explicit endpoint behind one ModelProvider
  interface. Use when wiring, swapping, or debugging the model the router and
  executor call.'
---

# Local Model Provider

OpenMolClaw calls a **configured model provider** through a single interface, so
the router and executor never care which model answers. The default path is
local, the recommended hosted path is OpenRouter ZDR, and any other
chat-completions-compatible endpoint can be selected explicitly.

## The interface

```python
class ModelProvider:
    def complete_with_tools(self, messages, tools, tool_choice):
        ...
```

## Local endpoint

Point at any local runtime that serves `/v1/chat/completions`:

```yaml
model:
  provider: local
  model: olmo
  endpoint: http://localhost:11434/v1
```

```python
from openmolclaw.config import build_provider, load_config
provider = build_provider(load_config("examples/config.local.olmo.yaml"))
```

No API key is required by default.

## OpenRouter ZDR endpoint

```yaml
model:
  provider: openrouter
  model: google/gemma-4-26b-a4b-it
  base_url: https://openrouter.ai/api/v1
  zdr: true
```

Set the key in the environment, never in the file:

```bash
export OPENROUTER_API_KEY=...
```

## Using it in the loop

```python
from openmolclaw.builtin_tools import build_default_registry
from openmolclaw.harness.router import Router
from openmolclaw.harness.executor import ToolExecutor

registry = build_default_registry()
router = Router(provider)
decision = router.route("Draw benzene.", registry.specs())
result = ToolExecutor(registry).execute_decision(decision)
```

## Bring your own endpoint

Name any provider when you also provide the exact endpoint:

```yaml
model:
  provider: openai
  model: gpt-4.1-mini
  endpoint: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY
```

For non-chat-completions APIs, implement `complete_with_tools` on any class and
pass the instance to `Router`. A host can wire its own backend behind this same
interface without touching harness code.

## Why this matters

- **Portability.** Swapping a local model for an OpenRouter-compatible one is a
  config change, not a code change.
- **No lock-in.** The harness depends on the interface, not on any vendor SDK.
- **Local-first.** The default path runs entirely on your machine.
- **Fail-closed.** OpenMolClaw never guesses an endpoint and never silently
  falls back to another model.

---
*Maintained by the [ChemIllusion](https://chemillusion.com) team as part of OpenMolClaw.*
