# Versioning & release policy

OpenMolClaw follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html):
`MAJOR.MINOR.PATCH`. This page defines what each level means **for this package**,
because the versions here are load-bearing downstream.

## Why semver is load-bearing here

Per the private/public split roadmap (`openmolclaw_private_public_split_prd.md`
§16, Phases 3–5), the private ChemIllusion product imports OpenMolClaw as a
**pinned, released** dependency — never a git ref. A breaking change to the
harness core therefore breaks a paying product until its pin is bumped. Semver
discipline and a truthful [CHANGELOG](../CHANGELOG.md) are how downstream
consumers know whether a bump is safe.

## What counts as a breaking change (MAJOR)

The **public API surface** under semver is:

- The adapter Protocols and value types in `openmolclaw.harness.interfaces`
  (`ModelProvider`, `UsageSink`, `ToolGate`, `WorkspaceStore`, `UsageEvent`,
  `ToolContext`, `GateResult`, `Workspace`) — signatures and field sets.
- The harness classes `Router`, `ToolExecutor`, `ToolRegistry` and their public
  constructor/method signatures.
- `openmolclaw.harness.schemas.RouterDecision` field set.
- The public chemistry tool functions in `openmolclaw.chemistry.*` (names,
  arguments, and canonical outputs pinned by the contract suite).
- The workspace serialization format and semantic-alias round-trip.
- The CLI subcommands and the HTTP contract in `docs/api_contracts.md`.

Changing any of the above incompatibly (removing/renaming, changing required
arguments, changing pinned outputs) is a **MAJOR** bump.

## MINOR / PATCH

- **MINOR** — backward-compatible additions: new tools, new optional arguments,
  new providers, new skills, additive config keys.
- **PATCH** — backward-compatible bug fixes and doc/internal changes with no API
  change.

`0.x` note: while pre-1.0, a MINOR bump may carry a breaking change **only** when
unavoidable, and it must be called out under a `### Changed` / `### Removed`
heading in the changelog with a migration note. Prefer a clean 1.0 once the
surface stabilizes.

## The contract suite is the tripwire

`tests/contract/` pins router decisions, schema validation, RDKit canonical
outputs, and workspace round-trips with byte-identical fixtures in both repos.
If a change moves a pinned output, that is by definition an API change — decide
MINOR-with-migration-note vs MAJOR accordingly, and coordinate the fixture
update across both repos in the same change.

## Release mechanics

Releases are tag-driven. See [GOVERNANCE.md](../GOVERNANCE.md) for the release
manager role and the exact steps; in short:

1. Land changes on `main`; update [CHANGELOG.md](../CHANGELOG.md) under the new
   version and move the `[Unreleased]` items down.
2. Bump `__version__` in `src/openmolclaw/__init__.py`.
3. Tag `vX.Y.Z` and push the tag — the release workflow builds, `twine check`s,
   and publishes to PyPI (see `scripts/install_release_workflow.sh`).
4. Downstream (private ChemIllusion) bumps its pin after the contract suite is
   green against the released wheel.
