# Contract tests (shared across repos)

These tests pin the behavior the public `openmolclaw` package and the private
ChemIllusion `agent_core` must agree on: router-decision parsing, router schema
validation, deterministic RDKit facts (canonical SMILES + InChIKey), and
workspace snapshot round-trips.

## How the sharing works

Three parts are **byte-identical** in both repos:

- `test_contract.py` — the assertions
- `fixtures/` — the inputs
- `expected/` — the expected outputs

Exactly one part differs per repo:

- `binding.py` — maps each abstract capability onto that repo's modules.
  - Public (`openmolclaw`): binds to `openmolclaw.*` — every capability present.
  - Private (`chem-art-generator`): binds to `app.agent_core.*`, and sets any
    not-yet-extracted capability (e.g. `workspace_roundtrip`) to `None`.

A capability whose binding is `None` is **skipped**, not failed. When both repos
implement a capability, the fixtures must produce the expected outputs to the
byte — a divergence fails the suite and appears in the weekly drift report
(PRD §12.3).

## Running

```bash
# public repo
pip install -e ".[dev]"
pytest tests/contract -q

# private repo
PYTHONPATH=backend pytest backend/tests/contract -q
```

## Updating fixtures

Change `fixtures/` and `expected/` together, and copy the identical files into
both repos in the same change. Never edit `expected/` in only one repo — that is
exactly the drift the contract exists to catch.
