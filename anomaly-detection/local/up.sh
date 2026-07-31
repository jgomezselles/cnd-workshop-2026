#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

RUN_DATALOADER="${RUN_DATALOADER:-1}"
STOP_OTHER_STACK="${STOP_OTHER_STACK:-0}"

usage() {
  cat <<'EOF'
Usage: ./up.sh [--with-dataloader|--skip-dataloader] [--reset-volumes|--keep-volumes] [--stop-other-stack|--keep-other-stack]

Defaults:
  - run the one-shot dataloader;
  - reset Docker volumes, so local development starts from a reproducible dataset.
  - keep the Cloud compose stack running; Cloud uses a separate host port range.

Options:
  --with-dataloader  Run the seed profile once before starting vmanomaly.
  --skip-dataloader  Reuse an already seeded dataset and start vmanomaly only.
  --reset-volumes    Remove Docker volumes before startup.
  --keep-volumes     Keep Docker volumes before startup.
  --stop-other-stack  Stop the Cloud compose stack before startup anyway.
  --keep-other-stack  Do not stop the Cloud compose stack.
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

  echo "Stopping cloud stack first to free shared demo ports..."
  docker compose -f ../cloud/docker-compose.yml --project-directory ../cloud down --remove-orphans
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
  docker compose down --volumes --remove-orphans
else
  docker compose down --remove-orphans
fi

if [[ "${RUN_DATALOADER}" == "1" ]]; then
  docker compose up -d victoriametrics vmagent alertmanager grafana vmalert
  # The dataloader writes through vmagent, and vmagent forwards to the local
  # VictoriaMetrics instance. Wait for both endpoints before seeding data.
  wait_http "VictoriaMetrics" "http://localhost:8428/health"
  wait_http "vmagent" "http://localhost:8429/health"
  # This command is blocking. With `set -e`, vmanomaly is started only after
  # the dataloader exits successfully.
  docker compose --profile seed run --rm dataloader
fi

docker compose up -d --remove-orphans
wait_http "vmanomaly" "http://localhost:8490/health"
wait_http "MCP server" "http://localhost:8081/health/liveness"

cat <<EOF

OTEL APM demo stack is starting.
  Grafana:         http://localhost:3000
  VictoriaMetrics: http://localhost:8428
  vmanomaly:       http://localhost:8490
  MCP server:      http://localhost:8081/mcp
  vmalert:         http://localhost:8880
  Alertmanager:    http://localhost:9093
  Alert webhook:   http://localhost:5001

Backfill window: ${VMANOMALY_BACKFILL_FROM} to ${VMANOMALY_BACKFILL_TO}
Dataloader:      $(if [[ "${RUN_DATALOADER}" == "1" ]]; then echo "ran once"; else echo "skipped"; fi)
AI Copilot:      $(if [[ "${VMANOMALY_COPILOT_ENABLED}" == "true" ]]; then echo "enabled (${VMANOMALY_COPILOT_MODEL})"; else echo "disabled; add .secret/ANTHROPIC_API_KEY to enable"; fi)
EOF
