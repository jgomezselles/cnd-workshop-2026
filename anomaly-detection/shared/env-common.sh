#!/usr/bin/env bash
set -euo pipefail

# vmanomaly backtesting needs absolute UTC timestamps. By default we replay
# the recent 3 days only; model training windows stay defined in the config.
BACKFILL_DAYS="${VMANOMALY_BACKFILL_DAYS:-3}"

export VMANOMALY_BACKFILL_FROM
export VMANOMALY_BACKFILL_TO

VMANOMALY_BACKFILL_FROM="$(date -u -d "${BACKFILL_DAYS} day ago" +"%Y-%m-%dT%H:%M:%SZ")"
VMANOMALY_BACKFILL_TO="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
