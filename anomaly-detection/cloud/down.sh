#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

if [[ "${1:-}" == "--keep-volumes" ]]; then
  docker compose down --remove-orphans
else
  # Removing volumes clears Grafana state and vmanomaly cloud model/data dumps.
  # It does not delete anything from VictoriaMetrics Cloud.
  docker compose down --volumes --remove-orphans
fi
