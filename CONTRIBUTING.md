# Contributing to OpenMolClaw

Thank you for helping improve OpenMolClaw. This repo is the public, local-first
chemistry agent harness from the team behind
[ChemIllusion](https://chemillusion.com).

## Sync policy (read this first)

Not every file here is edited the same way. Before you open a PR, read
[**docs/sync_policy.md**](docs/sync_policy.md).

| Class | How to contribute |
| ----- | ----------------- |
| **Public-owned** | Normal pull requests — package code, `tests/`, `docs/`, `examples/`, and **new** skills you add under `src/openmolclaw/skills/` |
| **Synced from private** | Patch proposals only — files with a `SYNCED FILE` generated header are exported from ChemIllusion; accepted changes are imported upstream and re-exported, so a direct edit may be overwritten |

**Contract tests** (`tests/contract/`) keep public and private behavior aligned.
They are byte-identical across repos except `binding.py`. When you change
fixtures or expected outputs, update both repos in the same change.

You are not being tricked: public-owned work merges here directly; synced work
is welcome but flows through the upstream export pipeline.

## Ways to contribute

### Chemistry skills

Skills are Markdown playbooks under `src/openmolclaw/skills/<name>/SKILL.md`.
They guide the agent; they are not executable plugins.

- **Propose a skill** — [New chemistry skill issue](https://github.com/scottmreed/openmolclaw/issues/new?template=new-chemistry-skill.yml)
- **Discuss ideas** — [Chemistry skills discussions](https://github.com/scottmreed/openmolclaw/discussions/categories/chemistry-skills)
- **Implement** — follow [docs/adding_skills.md](docs/adding_skills.md)

New skills you author are **public-owned** unless they replace a synced file.

### Callable tools

To register a tool the router can call, add a handler and schema in
`src/openmolclaw/builtin_tools.py`. See existing chemistry tools and
`tests/test_skill_registry.py`.

### Model providers

Provider configuration is explicit and fail-closed. See
[docs/model_providers.md](docs/model_providers.md). Questions and setup notes
belong in [Model providers discussions](https://github.com/scottmreed/openmolclaw/discussions/categories/model-providers).

### Documentation and examples

`docs/` and `examples/` are public-owned. Match the existing tone: local-first,
no secrets in committed config, link to related docs.

## Development setup

```bash
git clone https://github.com/scottmreed/openmolclaw.git
cd openmolclaw
pip install -e ".[dev]"
pytest -q
python -m openmolclaw doctor
```

See [docs/local_install.md](docs/local_install.md) for the full CLI reference.

## Pull request checklist

1. Scope matches the sync policy (public-owned vs patch proposal).
2. `pytest -q` passes.
3. No API keys, `.env` values, or other secrets in the diff.
4. Contract fixture changes are coordinated with the private repo when applicable.

## License

By contributing, you agree that your contributions are licensed under the
project's [Apache-2.0](LICENSE) license.
