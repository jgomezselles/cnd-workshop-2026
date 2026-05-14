#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Reuse the same backfill timestamp calculation as the local stack.
source "${SCRIPT_DIR}/../shared/env-common.sh"

read_secret_file() {
  local path="$1"

  if [[ ! -s "${path}" ]]; then
    echo "Missing or empty secret file: ${path}" >&2
    exit 1
  fi

  # Secret files should contain a single value. Strip CR/LF so the result is
  # safe for Docker Compose interpolation and vmanomaly env substitution.
  tr -d '\r\n' < "${path}"
}

read_optional_secret_file() {
  local path="$1"
  local default_value="$2"

  if [[ -s "${path}" ]]; then
    tr -d '\r\n' < "${path}"
  else
    printf "%s" "${default_value}"
  fi
}

export VM_CLOUD_READ_BEARER_TOKEN
export VM_CLOUD_WRITE_BEARER_TOKEN
export VM_CLOUD_DATASOURCE_URL
export VM_CLOUD_GRAFANA_DATASOURCE_URL
export VM_CLOUD_READ_GRAFANA_DATASOURCE_URL
export VM_CLOUD_REMOTE_WRITE_URL
export VM_CLOUD_READ_TENANT_ID
export VM_CLOUD_WRITE_TENANT_ID
export VM_CLOUD_READ_TENANT_ID_ESCAPED

VM_CLOUD_READ_BEARER_TOKEN="$(read_secret_file "${SCRIPT_DIR}/../.secret/BEARER_TOKEN_READ")"
VM_CLOUD_WRITE_BEARER_TOKEN="$(read_secret_file "${SCRIPT_DIR}/../.secret/BEARER_TOKEN_WRITE")"

VM_CLOUD_DATASOURCE_URL="$(read_secret_file "${SCRIPT_DIR}/../.secret/datasource_url")"
VM_CLOUD_READ_TENANT_ID="$(read_optional_secret_file "${SCRIPT_DIR}/../.secret/read_tenant_id" "0:101")"
VM_CLOUD_WRITE_TENANT_ID="$(read_optional_secret_file "${SCRIPT_DIR}/../.secret/write_tenant_id" "0:101")"
VM_CLOUD_READ_TENANT_ID_ESCAPED="${VM_CLOUD_READ_TENANT_ID//:/%3A}"

VM_CLOUD_BASE_URL="${VM_CLOUD_DATASOURCE_URL%/}"

if [[ "${VM_CLOUD_BASE_URL}" =~ ^(.*)/select/[0-9]+(:[0-9]+)?/prometheus(/.*)?$ ]]; then
  VM_CLOUD_BASE_URL="${BASH_REMATCH[1]}"
fi
VM_CLOUD_DATASOURCE_URL="${VM_CLOUD_BASE_URL}"

VM_CLOUD_READ_GRAFANA_DATASOURCE_URL="${VM_CLOUD_BASE_URL}/select/${VM_CLOUD_READ_TENANT_ID}/prometheus"

if [[ -s "${SCRIPT_DIR}/../.secret/grafana_datasource_url" ]]; then
  VM_CLOUD_GRAFANA_DATASOURCE_URL="$(read_secret_file "${SCRIPT_DIR}/../.secret/grafana_datasource_url")"
else
  # Grafana dashboards read anomaly scores and self-monitoring metrics from the
  # configured write tenant. For initial verification this matches the read
  # tenant; later workshops can split it per participant.
  VM_CLOUD_GRAFANA_DATASOURCE_URL="${VM_CLOUD_BASE_URL}/select/${VM_CLOUD_WRITE_TENANT_ID}/prometheus"
fi

if [[ -s "${SCRIPT_DIR}/../.secret/remote_write_url" ]]; then
  VM_CLOUD_REMOTE_WRITE_URL="$(read_secret_file "${SCRIPT_DIR}/../.secret/remote_write_url")"
else
  VM_CLOUD_REMOTE_WRITE_URL="${VM_CLOUD_BASE_URL}/prometheus/api/v1/write"
fi
