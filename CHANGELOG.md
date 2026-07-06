# Changelog

All notable changes to **OpenMolClaw** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
See [docs/versioning.md](docs/versioning.md) for what a breaking change means for
OpenMolClaw specifically — the private ChemIllusion product pins released
versions, so semver here is load-bearing.

## [Unreleased]

### Added
- Governance groundwork for the upstream-first transition (PRD §16 Phase 5):
  this changelog, a semver policy ([docs/versioning.md](docs/versioning.md)), a
  [GOVERNANCE.md](GOVERNANCE.md) describing repository roles and the release
  process, a `CODEOWNERS` file protecting the harness core, and a tag-driven
  PyPI release workflow installer (`scripts/install_release_workflow.sh`).

## [0.1.0] — 2026-07-06

Initial public release — the local-first chemistry agent harness from the team
behind [ChemIllusion](https://chemillusion.com).

### Added
- `openmolclaw` package (`src/` layout): router-first harness (`harness/router.py`,
  `executor.py`, `tool_registry.py`, `schemas.py`, adapter `interfaces.py`, and
  public-safe `defaults.py`).
- Model providers with explicit, fail-closed routing: `providers/local.py`,
  `providers/openrouter.py` (incl. OpenRouter **ZDR** support), and
  `providers/base.py`.
- RDKit-backed chemistry tools: `chemistry/rdkit_tools.py`, `render.py`,
  `validate.py`, `convert.py`, and PubChem `lookup.py`.
- Workspace state, semantic aliases, and JSON serialization (`workspace/`).
- Local Flask app + clean-room JS/Ketcher bridge (`app.py`, `web/`), plus a
  conversational chat endpoint (`harness/chat.py`).
- CLI: `python -m openmolclaw` with `doctor`, `serve`, `list-tools`,
  `run-contracts`, `privacy`, `version`, `install-ketcher`.
- **Privacy:** ZDR routing and Private Structure Mode (`config.py`
  `resolve_privacy_flags()`, `privacy.py`), surfaced via `GET /api/privacy`,
  the web Privacy panel, and [docs/zdr.md](docs/zdr.md).
- Six curated skills under `src/openmolclaw/skills/`.
- Shared contract suite (`tests/contract/`) — byte-identical fixtures/expected
  with the private repo, per-repo `binding.py`.
- Apache-2.0 `LICENSE` + `NOTICE`; ChemIllusion attribution throughout; PyPI-ready
  packaging (`twine check` clean — see [docs/publishing.md](docs/publishing.md)).

[Unreleased]: https://github.com/scottmreed/openmolclaw/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/scottmreed/openmolclaw/releases/tag/v0.1.0
