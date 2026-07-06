# Local install

OpenMolClaw is a small, local-first chemistry agent harness: a Ketcher editor, a
Flask app, RDKit tools, and a provider-neutral router→executor loop. Everything
runs on your machine, and nothing here needs a secret or a network connection.

## Requirements

- Python >= 3.10
- RDKit (installed automatically as a dependency)
- A model endpoint (only when you want the agent loop to call a model): a local
  chat-completions server, OpenRouter ZDR, or another explicit endpoint. See
  [`model_providers.md`](model_providers.md). The chemistry tools, validation,
  rendering, and workspace all work with no model configured.

## Install

```bash
pip install openmolclaw            # from a release
```

From a clone (src/ layout):

```bash
pip install -e ".[dev]"            # editable + test deps
pip install -e ".[dev,build]"      # also build/twine for packaging
```

The package uses a `src/openmolclaw` layout, so an editable install is the
reliable way to run it from a checkout.

## Check the install

```bash
python -m openmolclaw doctor
# or, via the console entry point:
openmolclaw doctor
```

`doctor` verifies RDKit, Flask, a sample render, a workspace round-trip, the
built-in tool registry, your model-provider config (described only — never
called), and the in-package contract suite. It exits non-zero if any core check
fails. Point it at a config with
`--config examples/config.local.olmo.yaml`.

## CLI commands

| Command | What it does |
|---|---|
| `openmolclaw doctor [--config FILE]` | Environment + contract self-check. |
| `openmolclaw serve [--host H --port P]` | Run the local Flask app + Ketcher UI. |
| `openmolclaw list-tools [--json]` | List the built-in chemistry tools (or full schemas). |
| `openmolclaw run-contracts` | Run the in-package contract suite (no network). |
| `openmolclaw version` | Print the package version. |

## Run the local app

```bash
openmolclaw serve            # http://127.0.0.1:5000
```

Useful routes: `/` (Ketcher UI), `/docs` (HTML API docs), `/api/health`,
`/api/tools`, `/api/contracts`. See [`api_contracts.md`](api_contracts.md).

The SMILES/RDKit tools and workspace work even before Ketcher is added. To add
Ketcher, install a Ketcher standalone build into the local app assets:

```bash
openmolclaw install-ketcher --archive /path/to/ketcher-standalone-build
```

`--archive` accepts a local build directory, a local zip/tar archive, or an
HTTPS URL to an archive. **Note:** current upstream `ketcher-standalone*.zip`
release assets (Ketcher 3.x) contain only the npm library, not a runnable
`index.html` — you need to build the demo page from source first. See
[`../src/openmolclaw/web/vendor/ketcher/README.md`](../src/openmolclaw/web/vendor/ketcher/README.md)
for the exact build steps.

## Run the tests

```bash
pytest -q                    # full suite (offline)
pytest tests/contract -q     # the shared cross-repo parity suite
python -m openmolclaw run-contracts   # the same public-API contracts, via the CLI
```

All tests run without network access or secrets. Provider smoke tests that would
call a live endpoint are opt-in via environment flags (see
[`model_providers.md`](model_providers.md)).
