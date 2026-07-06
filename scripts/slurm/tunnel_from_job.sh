#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/slurm/tunnel_from_job.sh --login user@login.cluster.edu --node compute-12.cluster.edu [--port 5000] [--local-port 5000]

Prints an SSH tunnel command for clusters where the login node can route to the
compute node.
USAGE
}

LOGIN=""
NODE=""
PORT="5000"
LOCAL_PORT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --login)
      LOGIN="${2:-}"
      shift 2
      ;;
    --node)
      NODE="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --local-port)
      LOCAL_PORT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$LOGIN" || -z "$NODE" ]]; then
  usage >&2
  exit 2
fi

LOCAL_PORT="${LOCAL_PORT:-$PORT}"

printf 'ssh -N -L %s:%s:%s %s\n' "$LOCAL_PORT" "$NODE" "$PORT" "$LOGIN"
