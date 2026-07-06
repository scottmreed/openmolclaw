# Continuous integration

OpenMolClaw's public CI (PRD §12.2) installs the package and runs the unit +
contract suites plus `openmolclaw doctor` on Python 3.10 and 3.12. The workflow
lives at `.github/workflows/ci.yml`.

## Why there's an install script

GitHub refuses to let a **fine-grained PAT or a GitHub App** create or update any
file under `.github/workflows/` unless the credential carries the `workflow`
scope. The automated tooling that authored this package has neither, so it
cannot commit the workflow file itself. Rather than hand-copy YAML, run the
committed helper from a checkout whose `git` credential *does* have `workflow`
scope (a normal local clone):

```bash
bash scripts/install_ci_workflow.sh          # write + commit locally
bash scripts/install_ci_workflow.sh --push   # write + commit + push HEAD
```

The script is idempotent: it rewrites `.github/workflows/ci.yml` to the canonical
content and only commits when something changed. Commit author defaults to
Scott's GitHub no-reply (override via `GIT_COMMITTER_NAME` / `GIT_COMMITTER_EMAIL`).

## What the workflow runs

```yaml
- pip install -e ".[dev]"
- openmolclaw doctor
- pytest tests -q     # unit + shared contract suite
```
