#!/usr/bin/env bash
# Follow compose logs.
#
# Usage:
#   ./scripts/docker-logs.sh
#   ./scripts/docker-logs.sh app

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."
exec docker compose logs --follow "$@"
