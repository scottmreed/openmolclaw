# OpenRouter ZDR Mode

OpenMolClaw is local-first: Ketcher, RDKit, and the chemistry tools run on your
machine, and OpenMolClaw does not send your structures to ChemIllusion servers
or require a ChemIllusion account. When you choose **OpenRouter** as your model
provider, you can enable **ZDR Mode** so OpenMolClaw adds per-request routing
controls that require Zero Data Retention (ZDR) endpoints, deny provider data
collection, and disable provider fallbacks.

This page explains exactly what ZDR Mode does and — just as important — what it
does **not** do.

## What ZDR Mode changes

When ZDR Mode is enabled and the provider is `openrouter`, every request carries
this provider-routing object:

```json
{
  "provider": {
    "zdr": true,
    "data_collection": "deny",
    "allow_fallbacks": false,
    "require_parameters": true
  }
}
```

- `zdr: true` restricts routing to endpoints with a Zero Data Retention policy.
- `data_collection: "deny"` avoids providers that may collect/store request data.
- `allow_fallbacks: false` prevents silent routing to a backup provider that may
  not honor the same policy.
- `require_parameters: true` only routes to endpoints that support the requested
  tool parameters.

OpenMolClaw fails **closed**: if no API key is set, or (with ZDR-endpoint
preflight enabled) no ZDR endpoint can be verified for the model, the request is
refused rather than sent to a non-ZDR endpoint.

## What ZDR Mode does not change

ZDR Mode applies **only** to requests this local OpenMolClaw app sends to
OpenRouter. It does not change:

- your OpenRouter account-level prompt-logging settings (check those separately
  in your own OpenRouter workspace),
- your operating system logs, browser extensions, proxies, or network monitors,
- fully local providers (no OpenRouter request is made, so ZDR routing is not
  applicable),
- custom `ModelProvider` implementations you write (they are outside the bundled
  provider's ZDR guarantee unless they implement comparable behavior),
- local workspace files you save on your own machine.

## Local provider vs OpenRouter vs custom provider

| Provider | ZDR routing | Notes |
|---|---|---|
| `local` | Not applicable | No OpenRouter request is made. |
| `openrouter` | Applied when ZDR Mode is on | Per-request routing controls above. |
| custom (your endpoint) | Not guaranteed | Only what your code implements. |

## OpenRouter endpoint retention vs local workspace files

These are two different things:

- **OpenRouter endpoint retention** is governed by ZDR Mode's per-request
  routing controls.
- **Local workspace files** are written by OpenMolClaw itself to
  `.openmolclaw/workspaces/<workspace_id>.json` when the render endpoint stores a
  molecule. That is retention on *your own machine*, not on any server.

## How to disable local disk persistence

Set the workspace save mode to `memory_only`:

```yaml
workspace:
  save_mode: memory_only
```

or

```bash
export OPENMOLCLAW_WORKSPACE_SAVE_MODE=memory_only
```

In memory-only mode, rendered structures are held in process memory for the app
session and are **not** written to `.openmolclaw/workspaces`. They still live in
RAM for the session, which is why the honest claim is "not written to disk by
OpenMolClaw", not "never retained anywhere". The local web UI also exposes a
"Do not save workspace to disk for this session" toggle.

## Enabling ZDR Mode

Config file:

```yaml
model:
  provider: openrouter
  model: allenai/olmo-2-0325-32b-instruct
  base_url: https://openrouter.ai/api/v1
  privacy:
    openrouter_zdr: true
    deny_data_collection: true
    allow_fallbacks: false
    require_parameters: true
```

Environment variables (override config defaults):

```bash
export OPENMOLCLAW_OPENROUTER_ZDR=1
export OPENMOLCLAW_OPENROUTER_DENY_DATA_COLLECTION=1
export OPENMOLCLAW_OPENROUTER_ALLOW_FALLBACKS=0
export OPENMOLCLAW_OPENROUTER_REQUIRE_PARAMETERS=1
export OPENMOLCLAW_WORKSPACE_SAVE_MODE=memory_only
# Optional live ZDR-endpoint preflight (off by default):
export OPENMOLCLAW_OPENROUTER_ZDR_PREFLIGHT=1
```

Precedence (highest wins): explicit config value → environment variable → safe
default. ZDR routing is **off by default** (opt-in) because requiring ZDR
endpoints can reduce model/provider availability; provider data collection is
denied and fallbacks are disabled by default.

Inspect the resolved posture without touching the network:

```bash
python -m openmolclaw privacy --config examples/config.openrouter.zdr.yaml
python -m openmolclaw privacy --json
```

or, from the running app, `GET /api/privacy`.

## Feature-loss warnings

When ZDR Mode is enabled:

- Some models may fail if no ZDR-compatible endpoint supports tool calls.
- Requests may cost more or be slower because provider routing is restricted.
- Fallbacks are disabled, so uptime may be lower.
- Local workspace files are still saved unless memory-only mode is enabled.
- ZDR does not apply to local providers because no OpenRouter request is made.

## Private Structure Mode

ZDR Mode alone only covers the OpenRouter request. **Private Structure Mode** is
a single toggle (`model.privacy.private_structure_mode`, the UI checkbox, or
`OPENMOLCLAW_PRIVATE_STRUCTURE_MODE=1`) that combines everything OpenMolClaw can
control for a structure-bearing session:

- **ZDR-compatible AI routing when AI is required.** For `openrouter` it forces
  `openrouter_zdr`, `deny_data_collection`, and `require_parameters` on and
  `allow_fallbacks` off — enabling Private Structure Mode can only *strengthen*
  these, never silently weaken them. For `local` no request ever leaves the
  machine, so the clause is trivially satisfied.
- **No external molecule lookups.** The `lookup_compound` tool (PubChem name
  resolution) is blocked outright — the lookup query itself would leave the
  machine, independent of which AI provider is configured.
- **No disk persistence.** The workspace is forced to memory-only
  (`workspace_save_mode: memory_only`); rendered structures live only in
  process memory for the session unless you explicitly export them.

When — and only when — all three hold, `GET /api/privacy` and
`openmolclaw privacy` report a `private_structure_mode_claim`:

> Private Structure Mode: structures are processed only for the active
> request, routed through ZDR-compatible AI providers where AI is required,
> excluded from model training, excluded from external molecule lookups, and
> not saved to projects or chat history unless you explicitly choose to save
> them.

This mirrors ChemIllusion's researcher-exclusive "Private Structure Mode"
claim, scoped down for a single-user local app — there is no role gating here
because whoever runs `openmolclaw serve` is the only user.

**The claim is deliberately withheld for a custom (non-`local`,
non-`openrouter`) endpoint.** OpenMolClaw cannot verify an arbitrary endpoint's
retention policy, so it still blocks external lookups and forces memory-only
under Private Structure Mode, but `private_structure_mode_claim` stays `null`
and a warning explains why.

## Claims to avoid

Do not claim "no one can ever see your structures", "no data is retained
anywhere", "guaranteed private", or "ZDR applies to local files". ZDR Mode still
requires transient processing at the chosen endpoint, and OpenRouter notes that
prompt caching can occur in memory under ZDR. Only surface the
`private_structure_mode_claim` sentence itself — do not paraphrase it into a
stronger claim, and never show it when the resolved posture doesn't actually
satisfy all three conditions above.
