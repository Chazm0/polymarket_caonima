#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1091
source .venv/bin/activate

pm migrate
pm ingest-markets --pages "${PAGES:-1}" --limit "${LIMIT:-1000}"

# You still need to track markets explicitly (or implement an auto-tracker).
# Example:
# pm track-markets --session manual --market-ids 123,456

pm collect-orderbooks --iterations "${ITERS:-3}"