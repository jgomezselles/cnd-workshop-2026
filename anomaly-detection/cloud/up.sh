#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

RUN_DATALOADER="${RUN_DATALOADER:-0}"
STOP_OTHER_STACK="${STOP_OTHER_STACK:-0}"
COMPOSE=(docker compose)

usage() {
  cat <<'EOF'
Usage: ./up.sh [--with-dataloader|--skip-dataloader] [--reset-volumes|--keep-volumes] [--stop-other-stack|--keep-other-stack]

Defaults:
  - skip the one-shot dataloader;
  - keep local Grafana/vmanomaly/vmagent volumes.
  - keep the Local compose stack running; Cloud uses a separate host port range.

Options:
  --with-dataloader  Run the seed profile once before starting vmanomaly.
  --skip-dataloader  Reuse an already seeded Cloud dataset and start vmanomaly only.
  --reset-volumes    Remove local Docker volumes before startup.
  --keep-volumes     Keep local Docker volumes before startup.
  --stop-other-stack  Stop the Local compose stack before startup anyway.
  --keep-other-stack  Do not stop the Local compose stack.
EOF
}

wait_http() {
  local name="$1"
  local url="$2"
  local timeout="${3:-120}"
  local deadline

  deadline=$((SECONDS + timeout))
  until curl -fsS "${url}" >/dev/null; do
    if (( SECONDS >= deadline )); then
      echo "${name} did not become ready within ${timeout}s: ${url}" >&2
      return 1
    fi
    sleep 2
  done
}

stop_other_stack() {
  if [[ "${STOP_OTHER_STACK}" != "1" ]]; then
    return
  fi

  echo "Stopping local stack first to free shared demo ports..."
  docker compose -f ../local/docker-compose.yml --project-directory ../local down --remove-orphans
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-dataloader|--seed)
      RUN_DATALOADER=1
      ;;
    --skip-dataloader|--without-dataloader|--no-dataloader)
      RUN_DATALOADER=0
      ;;
    --reset-volumes)
      RESET_VOLUMES=1
      ;;
    --keep-volumes)
      RESET_VOLUMES=0
      ;;
    --stop-other-stack)
      STOP_OTHER_STACK=1
      ;;
    --keep-other-stack)
      STOP_OTHER_STACK=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

if [[ ! -s ../.secret/license ]]; then
  echo "Missing anomaly-detection/.secret/license. Put your vmanomaly license there before starting the stack." >&2
  exit 1
fi

source ./env.sh
stop_other_stack

if [[ -z "${RESET_VOLUMES+x}" ]]; then
  if [[ "${RUN_DATALOADER}" == "1" ]]; then
    RESET_VOLUMES=1
  else
    RESET_VOLUMES=0
  fi
fi

if [[ "${RESET_VOLUMES}" == "1" ]]; then
  "${COMPOSE[@]}" down --volumes --remove-orphans
else
  "${COMPOSE[@]}" down --remove-orphans
fi

if [[ "${RUN_DATALOADER}" == "1" ]]; then
  "${COMPOSE[@]}" up -d vmagent alertmanager grafana
  # Cloud seeding writes through the local vmagent relay. This blocks until
  # vmagent is ready; the remote Cloud endpoint is handled by vmagent buffering.
  wait_http "vmagent" "http://localhost:18429/health"
  # This command is blocking. With `set -e`, vmanomaly is started only after
  # the dataloader exits successfully.
  "${COMPOSE[@]}" --profile seed run --rm dataloader
fi

"${COMPOSE[@]}" up -d --remove-orphans

cat <<EOF

OTEL APM cloud demo stack is starting.
  Grafana:      http://localhost:13000
  vmanomaly:    http://localhost:18490
  vmagent:      http://localhost:18429
  vmalert:      http://localhost:18880
  Alertmanager: http://localhost:19093
  Alert webhook: http://localhost:15001

Cloud datasource base: ${VM_CLOUD_DATASOURCE_URL}
Read tenant:       ${VM_CLOUD_READ_TENANT_ID}
Write tenant:      ${VM_CLOUD_WRITE_TENANT_ID}
Grafana datasource: ${VM_CLOUD_GRAFANA_DATASOURCE_URL}
Cloud remote write: ${VM_CLOUD_REMOTE_WRITE_URL}
Backfill window:  ${VMANOMALY_BACKFILL_FROM} to ${VMANOMALY_BACKFILL_TO}
Dataloader:       $(if [[ "${RUN_DATALOADER}" == "1" ]]; then echo "ran once"; else echo "skipped"; fi)
EOF
