#!/usr/bin/env bash
# Run T-Syncer from the working tree with reload (no Docker).
#
# Usage:
#   ./scripts/local-setup.sh   # first time
#   ./scripts/local-run.sh
#
# Env overrides:
#   VENV_DIR   (default: <repo>/.venv)
#   HOST       (default: 127.0.0.1 — not TSYNCER_HOST, which is 0.0.0.0 for Compose)
#   PORT       (default: TSYNCER_PORT from .env, else 7100)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT/.venv}"
PYTHON="$VENV_DIR/bin/python"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"

if [[ ! -x "$PYTHON" ]] || ! "$PYTHON" -c "import sys" >/dev/null 2>&1; then
  echo "No usable venv at $VENV_DIR." >&2
  echo "Run ./scripts/local-setup.sh first." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  echo "Copy .env.example to .env and fill in TSYNCER_BASIC_USER / TSYNCER_BASIC_PASSWORD." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${TSYNCER_BASIC_USER:?TSYNCER_BASIC_USER must be set in .env}"
: "${TSYNCER_BASIC_PASSWORD:?TSYNCER_BASIC_PASSWORD must be set in .env}"

# A development server stays on loopback even when .env is set for Docker.
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-${TSYNCER_PORT:-7100}}"

cd "$ROOT"

# The package is normally installed editable by local-setup.sh, which puts `api`
# on the path. Fall back to the working tree so the server also starts in a venv
# that only has the dependencies -- this is the layout Dockerfile uses too.
export PYTHONPATH="$ROOT/t_syncer${PYTHONPATH:+:$PYTHONPATH}"

exec "$PYTHON" -m uvicorn api.app:create_app_from_settings \
  --factory \
  --reload \
  --reload-dir "$ROOT/t_syncer" \
  --host "$HOST" \
  --port "$PORT"
