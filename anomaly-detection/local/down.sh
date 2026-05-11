#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

if [[ "${1:-}" == "--keep-volumes" ]]; then
  docker compose down --remove-orphans
else
  # Removing volumes clears generated metrics and model state for the next run.
  docker compose down --volumes --remove-orphans
fi
