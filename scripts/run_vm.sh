#!/usr/bin/env bash
set -euo pipefail

PORT="${OPENMOLCLAW_PORT:-5000}"
CONFIG="${OPENMOLCLAW_CONFIG:-examples/config.remote.openrouter.zdr.yaml}"
WORKSPACE_ID="${OPENMOLCLAW_WORKSPACE_ID:-vm}"

python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .

python -m openmolclaw doctor --config "$CONFIG"

exec python -m openmolclaw serve \
  --host 127.0.0.1 \
  --port "$PORT" \
  --config "$CONFIG" \
  --workspace-id "$WORKSPACE_ID"
