#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1091
source .venv/bin/activate

# Optional env overrides:
# BATCH=50 TOP_N=10 LOOP=2 PER_BATCH_SLEEP=0.1 ITERS=0 ./scripts/collect_orderbooks.sh

BATCH="${BATCH:-}"
TOP_N="${TOP_N:-}"
LOOP="${LOOP:-}"
PER_BATCH_SLEEP="${PER_BATCH_SLEEP:-0.1}"
ITERS="${ITERS:-0}"

ARGS=("collect-orderbooks" "--per-batch-sleep" "$PER_BATCH_SLEEP" "--iterations" "$ITERS")
if [ -n "$BATCH" ]; then ARGS+=("--batch" "$BATCH"); fi
if [ -n "$TOP_N" ]; then ARGS+=("--top-n" "$TOP_N"); fi
if [ -n "$LOOP" ]; then ARGS+=("--loop-seconds" "$LOOP"); fi

pm "${ARGS[@]}"