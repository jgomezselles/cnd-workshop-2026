#!/usr/bin/env bash
set -euo pipefail

# vmanomaly backtesting needs absolute UTC timestamps. By default we replay
# the recent 3 days only; model training windows stay defined in the config.
BACKFILL_DAYS="${VMANOMALY_BACKFILL_DAYS:-3}"

export VMANOMALY_BACKFILL_FROM
export VMANOMALY_BACKFILL_TO

utc_now() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

utc_days_ago() {
  local days="$1"

  # GNU date, used by most Linux distributions and by normal WSL2 shells on
  # Windows. This path does not require python3.
  if date -u -d "${days} day ago" +"%Y-%m-%dT%H:%M:%SZ" >/dev/null 2>&1; then
    date -u -d "${days} day ago" +"%Y-%m-%dT%H:%M:%SZ"
    return
  fi

  # BSD date, used by macOS.
  if date -u -v-"${days}"d +"%Y-%m-%dT%H:%M:%SZ" >/dev/null 2>&1; then
    date -u -v-"${days}"d +"%Y-%m-%dT%H:%M:%SZ"
    return
  fi

  # Last-resort fallback for unusual environments.
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$days" <<'PY'
from datetime import datetime, timedelta, timezone
import sys

days = int(sys.argv[1])
print((datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ"))
PY
    return
  fi

  echo "Cannot compute UTC timestamp: unsupported date command and python3 not found" >&2
  return 1
}

VMANOMALY_BACKFILL_FROM="$(utc_days_ago "${BACKFILL_DAYS}")"
VMANOMALY_BACKFILL_TO="$(utc_now)"
