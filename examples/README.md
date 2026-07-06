# Examples

- `config.local.olmo.yaml` — a local OLMo-style model over a local
  chat-completions endpoint.
- `config.openrouter.standard.yaml` — OpenRouter with ZDR routing **off** (the
  privacy-forward defaults — deny data collection, no fallbacks — still apply).
- `config.openrouter.zdr.yaml` — OpenRouter ZDR routing with a tool-capable
  model (`export OPENROUTER_API_KEY=...`).
- `quickstart_workspace.json` — a two-molecule workspace snapshot you can load
  with the local JSON workspace store.
- `example_prompts.md` — prompts that exercise the router → executor loop.

Verify a config end-to-end:

```bash
openmolclaw doctor --config examples/config.openrouter.zdr.yaml
```
