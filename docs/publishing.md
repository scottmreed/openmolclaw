# Publishing OpenMolClaw to PyPI

OpenMolClaw is a real, `src/`-layout package: a built wheel is self-contained
(web UI, skills, and contract data all ship as package data) and installs and
runs from any directory with no source checkout.

## Versioning (single source of truth)

The version lives in exactly one place: `openmolclaw.__version__`
(`src/openmolclaw/__init__.py`). `pyproject.toml` reads it dynamically:

```toml
[project]
dynamic = ["version"]

[tool.setuptools.dynamic]
version = { attr = "openmolclaw.__version__" }
```

To cut a release, bump `__version__` and commit — the metadata follows.

## Build

```bash
pip install -e ".[build]"      # build + twine
python -m build                # -> dist/*.whl and dist/*.tar.gz
```

## Verify before upload

```bash
python -m twine check dist/*   # metadata + long-description render check
```

Confirm the package data actually shipped in the wheel:

```bash
python - <<'PY'
import glob, zipfile
z = zipfile.ZipFile(glob.glob("dist/*.whl")[0])
for pat in ("web/", "skills/", "contracts/data/", "py.typed", ".dist-info/licenses/"):
    print(pat, sum(pat in n for n in z.namelist()))
PY
```

A clean-room smoke test (fresh venv, install the wheel, run from an unrelated
directory) proves there are no source-path assumptions:

```bash
python -m venv /tmp/omc-clean && . /tmp/omc-clean/bin/activate
pip install dist/openmolclaw-*.whl
cd /tmp
openmolclaw doctor
openmolclaw run-contracts
```

## Upload

Test index first, then production:

```bash
python -m twine upload --repository testpypi dist/*
python -m twine upload dist/*
```

Use a PyPI API token (`__token__` / `pypi-...`) via `~/.pypirc` or the
`TWINE_USERNAME` / `TWINE_PASSWORD` environment variables. Never commit tokens.

## What ships in the distribution

- The `openmolclaw` package (`src/` layout).
- Package data: `web/**`, `skills/**`, `contracts/data/*.json`, `py.typed`.
- `LICENSE`, `NOTICE`, `THIRD_PARTY_NOTICES.md`, and `licenses/*` — the
  project's own Apache-2.0 license plus upstream license text for
  third-party components (RDKit, Flask, Ketcher). These are listed
  explicitly via `license-files` in `pyproject.toml` (setuptools' default
  `LICEN[CS]E*`/`NOTICE*` glob would otherwise silently drop
  `THIRD_PARTY_NOTICES.md` and `licenses/`), so they land in the sdist and in
  the wheel's `*.dist-info/licenses/`. See
  [`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) for what's covered
  and why — add new entries there and to `license-files` together whenever a
  new dependency or vendored component shows up.
- Console entry point: `openmolclaw = openmolclaw.__main__:main`.

Runtime dependencies: `rdkit`, `flask`, `pydantic`, `pyyaml`, `requests`. The
`dev` extra adds `pytest`; the `build` extra adds `build` + `twine`.

> **Note on the private/public split (PRD).** This document is the runbook for
> the first PyPI publish. The package is already PyPI-ready (`twine check`
> passes), so publishing is a release decision rather than more engineering —
> see the split PRD's Phase 3 for how a released, pinned version unblocks the
> private repo importing `openmolclaw`.
