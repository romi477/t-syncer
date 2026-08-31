#!/usr/bin/env bash
# Start T-Syncer in Docker (detached). All Compose values come from .env.
#
# Usage:
#   cp .env.example .env   # then fill in Basic Auth
#   ./scripts/docker-run.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"

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
: "${TSYNCER_HOST:?TSYNCER_HOST must be set in .env}"
: "${TSYNCER_PORT:?TSYNCER_PORT must be set in .env}"
: "${TSYNCER_SQLITE_DB_PATH:?TSYNCER_SQLITE_DB_PATH must be set in .env}"

cd "$ROOT"

if [[ "$TSYNCER_SQLITE_DB_PATH" = /* ]]; then
  DB_FILE="$TSYNCER_SQLITE_DB_PATH"
else
  DB_FILE="$ROOT/$TSYNCER_SQLITE_DB_PATH"
fi
mkdir -p "$(dirname "$DB_FILE")"
# Bind-mount target must exist as a file, not a directory.
if [[ ! -f "$DB_FILE" ]]; then
  touch "$DB_FILE"
fi

docker compose up --build --detach "$@"
docker compose ps

echo "T-Syncer: http://127.0.0.1:${TSYNCER_PORT}/web  (loopback only)"
echo "Health:   curl http://127.0.0.1:${TSYNCER_PORT}/health"
echo "Logs:     ./scripts/docker-logs.sh"
