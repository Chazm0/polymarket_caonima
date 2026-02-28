#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1091
source .venv/bin/activate

# Optional env overrides:
# EVENT_ID=123 PAGES=2 LIMIT=1000 ./scripts/ingest_markets.sh

ARGS=("ingest-markets")
if [ -n "${EVENT_ID:-}" ]; then ARGS+=("--event-id" "$EVENT_ID"); fi
ARGS+=("--pages" "${PAGES:-1}")
ARGS+=("--limit" "${LIMIT:-1000}")

pm "${ARGS[@]}"