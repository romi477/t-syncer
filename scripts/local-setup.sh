#!/usr/bin/env bash
# Create a local virtualenv with uv and install the package (with test extras).
#
# Usage:
#   ./scripts/local-setup.sh
#
# Env overrides:
#   VENV_DIR   (default: <repo>/.venv)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT/.venv}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

cd "$ROOT"

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "Created .env from .env.example — fill in TSYNCER_BASIC_USER and TSYNCER_BASIC_PASSWORD."
fi

export UV_PROJECT_ENVIRONMENT="$VENV_DIR"
uv sync --extra dev

echo "Installed tsyncer (dev extras) into $VENV_DIR"
echo "Next: edit .env, then ./scripts/local-run.sh"
