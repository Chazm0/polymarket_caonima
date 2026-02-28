#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1091
source .venv/bin/activate

# Usage:
#   ./scripts/track_markets.sh manual 123,456
SESSION="${1:-}"
MARKET_IDS="${2:-}"

if [ -z "$SESSION" ] || [ -z "$MARKET_IDS" ]; then
  echo "Usage: ./scripts/track_markets.sh <session> <market_ids_csv>"
  echo "Example: ./scripts/track_markets.sh manual 123,456"
  exit 2
fi

pm track-markets --session "$SESSION" --market-ids "$MARKET_IDS"