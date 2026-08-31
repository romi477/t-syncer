#!/usr/bin/env bash
# Build the container image through compose, so the build context and image tag
# have one definition.
#
# Usage:
#   ./scripts/docker-build.sh

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."
exec docker compose build "$@"
