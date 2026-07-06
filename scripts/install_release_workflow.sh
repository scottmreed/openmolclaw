#!/usr/bin/env bash
#
# install_release_workflow.sh — write, commit, and (optionally) push the public
# OpenMolClaw release workflow (.github/workflows/release.yml).
#
# WHY THIS EXISTS
# ---------------
# GitHub refuses to let a fine-grained PAT *or* a GitHub App create/update files
# under `.github/workflows/` unless the credential carries the `workflow` scope.
# The Hyperagent automation that staged the Phase 5 governance groundwork has
# neither, so it cannot land this file itself. Run this script yourself (your
# local `git` uses a credential that has the `workflow` scope) to add it. This
# mirrors scripts/install_ci_workflow.sh.
#
# USAGE
#   bash scripts/install_release_workflow.sh          # write + commit locally
#   bash scripts/install_release_workflow.sh --push   # write + commit + push HEAD
#
# ONE-TIME PyPI SETUP (before the first tagged release)
#   Configure PyPI Trusted Publishing (OIDC) for the `openmolclaw` project:
#   PyPI → project → Publishing → add a trusted publisher pointing at
#   scottmreed/openmolclaw, workflow `release.yml`, environment `pypi`.
#   No API token is stored in the repo. See docs/publishing.md.
#
# It is idempotent: re-running rewrites the file to the canonical content and
# only commits when something actually changed.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

WF_DIR=".github/workflows"
WF_FILE="$WF_DIR/release.yml"
mkdir -p "$WF_DIR"

cat > "$WF_FILE" <<'YAML'
name: release

# Tag-driven PyPI release (PRD §16 Phase 5). Pushing a `vX.Y.Z` tag builds the
# package, verifies metadata with `twine check`, runs the gate, and publishes to
# PyPI via Trusted Publishing (OIDC — no stored token).
on:
  push:
    tags:
      - "v*.*.*"

permissions:
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install build + test deps
        run: |
          python -m pip install --upgrade pip
          pip install build twine
          pip install -e ".[dev]"
      - name: Gate (doctor + tests)
        run: |
          openmolclaw doctor
          pytest tests -q
      - name: Verify tag matches package version
        run: |
          TAG="${GITHUB_REF_NAME#v}"
          PKG="$(python -c 'import openmolclaw; print(openmolclaw.__version__)')"
          if [ "$TAG" != "$PKG" ]; then
            echo "::error::tag v$TAG != package version $PKG"; exit 1
          fi
      - name: Build sdist + wheel
        run: python -m build
      - name: twine check
        run: twine check dist/*
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/

  publish:
    needs: build
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write   # required for PyPI Trusted Publishing (OIDC)
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
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
  commit -q -m "ci: add tag-driven PyPI release workflow (build + twine check + trusted publish)"
echo ">> committed $WF_FILE"

if [[ "${1:-}" == "--push" ]]; then
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  echo ">> pushing $BRANCH to origin"
  git push origin "HEAD:$BRANCH"
else
  echo ">> not pushed. Push with: git push origin HEAD"
fi
