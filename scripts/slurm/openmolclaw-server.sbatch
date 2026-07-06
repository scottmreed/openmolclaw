#!/usr/bin/env bash
#SBATCH --job-name=openmolclaw
#SBATCH --output=logs/openmolclaw-%j.out
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G

set -euo pipefail

PORT="${OPENMOLCLAW_PORT:-5000}"
HOST="${OPENMOLCLAW_HOST:-127.0.0.1}"
CONFIG="${OPENMOLCLAW_CONFIG:-examples/config.remote.openrouter.zdr.yaml}"
WORKSPACE_ID="${OPENMOLCLAW_WORKSPACE_ID:-slurm-${SLURM_JOB_ID}}"

mkdir -p logs

echo "OPENMOLCLAW_JOB_ID=${SLURM_JOB_ID}"
echo "OPENMOLCLAW_NODE=$(hostname -f)"
echo "OPENMOLCLAW_HOST=${HOST}"
echo "OPENMOLCLAW_PORT=${PORT}"
echo "OPENMOLCLAW_WORKSPACE_ID=${WORKSPACE_ID}"

python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .

python -m openmolclaw doctor --config "$CONFIG"

exec python -m openmolclaw serve \
  --host "$HOST" \
  --port "$PORT" \
  --config "$CONFIG" \
  --workspace-id "$WORKSPACE_ID"
