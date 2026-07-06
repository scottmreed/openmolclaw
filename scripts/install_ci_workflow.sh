#!/usr/bin/env bash
#
# install_ci_workflow.sh — write, commit, and (optionally) push the public
# OpenMolClaw CI workflow (.github/workflows/ci.yml).
#
# WHY THIS EXISTS
# ---------------
# GitHub refuses to let a fine-grained PAT *or* a GitHub App create/update files
# under `.github/workflows/` unless the credential carries the `workflow` scope.
# The Hyperagent automation that authored the Phase 2 package has neither, so it
# cannot land this file itself. Run this script yourself (your local `git` uses a
# credential that has the `workflow` scope) to add the workflow.
#
# USAGE
#   bash scripts/install_ci_workflow.sh            # write + commit locally
#   bash scripts/install_ci_workflow.sh --push     # write + commit + push HEAD
#
# It is idempotent: re-running rewrites the file to the canonical content and
# only commits when something actually changed.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

WF_DIR=".github/workflows"
WF_FILE="$WF_DIR/ci.yml"
mkdir -p "$WF_DIR"

cat > "$WF_FILE" <<'YAML'
name: ci

# Public OpenMolClaw CI (PRD §12.2): install the package, run the unit +
# contract suites, and check the doctor command.
on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
      - name: Doctor
        run: openmolclaw doctor
      - name: Unit + contract tests
        run: pytest tests -q
YAML

echo ">> wrote $WF_FILE"

if git diff --quiet -- "$WF_FILE" && git ls-files --error-unmatch "$WF_FILE" >/dev/null 2>&1; then
  echo ">> no changes — workflow already up to date."
  exit 0
fi

git add "$WF_FILE"
# Author as Scott's GitHub no-reply so downstream deploy checks stay happy.
# NB: assign the apostrophe-containing default in its own statement — a single
# quote inside "${VAR:-Scott's ...}" trips some shells' parser.
GIT_NAME="${GIT_COMMITTER_NAME:-}"
if [[ -z "$GIT_NAME" ]]; then GIT_NAME="Scott's Hyperagent"; fi
GIT_EMAIL="${GIT_COMMITTER_EMAIL:-53488644+scottmreed@users.noreply.github.com}"
git -c user.name="$GIT_NAME" -c user.email="$GIT_EMAIL" \
  commit -q -m "ci: add public OpenMolClaw CI (unit + contract + doctor)"
echo ">> committed $WF_FILE"

if [[ "${1:-}" == "--push" ]]; then
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  echo ">> pushing $BRANCH to origin"
  git push origin "HEAD:$BRANCH"
else
  echo ">> not pushed. Push with: git push origin HEAD"
fi
