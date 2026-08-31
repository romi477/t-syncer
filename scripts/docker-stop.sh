#!/usr/bin/env bash
# Stop the compose stack.
#
# Usage:
#   ./scripts/docker-stop.sh

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."
exec docker compose down "$@"
