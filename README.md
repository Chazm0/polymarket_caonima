# Polymarket Pipeline

A Postgres-first pipeline for ingesting Polymarket market metadata and live orderbook snapshots, computing microstructure features, and exporting clean datasets.

---

## Architecture

```
Gamma API ──► ingest-markets ──► markets (Postgres)
                                        │
                               auto-track / track-markets
                                        │
                               tracked_markets (Postgres)
                                        │
CLOB API ──► collect-orderbooks ──► orderbook_snapshots
                                        │
                               features_orderbook
                                        │
                               export ──► clean_orderbook_dataset.csv
```

---

## Prerequisites

- Python 3.10+
- A running Postgres database (local or [Neon](https://neon.tech))

---

## Installation

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1

# On Windows PowerShell — if activation is blocked:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 2. Install the package in editable mode
pip install -e .

# 3. Confirm CLI is available
pm --help
```

---

## Configuration

Create a `.env` file in the project root:

```env
# Required
DATABASE_DSN_PG=postgresql://user:password@host:5432/dbname?sslmode=require

# Optional — defaults shown
GAMMA_BASE=https://gamma-api.polymarket.com
CLOB_BASE=https://clob.polymarket.com
DEFAULT_BATCH_SIZE=50
DEFAULT_TOP_N=10
DEFAULT_LOOP_SECONDS=2.0
DEFAULT_STATEMENT_TIMEOUT_MS=60000
PM_USER_AGENT=polymarket-pipeline/0.1.0
```

`DATABASE_DSN_PG` is the only required variable.

---

## Step-by-step

### 1. Apply migrations

Run once (idempotent — safe to re-run):

```bash
pm migrate
```

Creates these tables:

| Table | Purpose |
|---|---|
| `markets` | Market metadata from Gamma API |
| `tracked_markets` | Markets selected for orderbook collection |
| `orderbook_snapshots` | Raw L2 book snapshots per token, time-series |
| `features_orderbook` | Derived microstructure features per snapshot |
| `schema_migrations` | Migration tracking (internal) |

---

### 2. Ingest markets

Pull active market metadata from the Gamma API into `markets`:

```bash
pm ingest-markets --pages 5 --limit 1000
```

| Flag | Default | Description |
|---|---|---|
| `--pages` | `1` | Number of pages to fetch |
| `--limit` | `1000` | Markets per page |
| `--event-id` | none | Restrict to a specific event ID |

Markets are upserted — re-running is safe. The ingester only stores active markets (skips closed, resolved, and markets ended >30 days ago).

Verify:

```sql
SELECT COUNT(*) AS n, MAX(end_time) FROM markets;
```

---

### 3. Select markets to track

#### Option A — Auto-track (recommended)

Selects the top N markets from `markets` ranked by liquidity → volume → recency and inserts them into `tracked_markets`.

```bash
pm auto-track --session my_session --top 200
```

Common examples:

```bash
# Only markets with at least $5k liquidity
pm auto-track --session liq5k --top 100 --min-liquidity 5000

# Only markets ending within the next 24 hours
pm auto-track --session ending_soon --top 50 --ends-within-hours 24

# Filter by category
pm auto-track --session politics --top 100 --category Politics

# Dry run — prints what would be tracked, no writes
pm auto-track --session test --top 50 --dry-run
```

| Flag | Default | Description |
|---|---|---|
| `--session` | **required** | Label stored in `tracked_markets.sessions[]` |
| `--top` | `200` | Max markets to select |
| `--min-liquidity` | none | Minimum `liquidity_num` |
| `--min-volume` | none | Minimum `volume_num` |
| `--ends-within-hours` | none | Only markets ending within N hours |
| `--category` | none | Filter by category string |
| `--include-closed` | false | Also include closed/resolved markets |
| `--include-already-tracked` | false | Re-add markets already in `tracked_markets` |
| `--allow-missing-token-keys` | false | Include markets without `clobTokenIds` in raw JSON |
| `--dry-run` | false | Print selection without writing |

#### Option B — Manual track

Track specific market IDs directly:

```bash
pm track-markets --session my_session --market-ids 123456,789012
```

---

### 4. Collect orderbooks

Polls the CLOB API for every token in non-ended tracked markets, stores raw snapshots, and computes features inline. Runs indefinitely by default.

```bash
pm collect-orderbooks
```

Common usage:

```bash
# Fixed number of iterations then exit
pm collect-orderbooks --iterations 100

# One-shot pass (no loop)
pm collect-orderbooks --iterations 1 --loop-seconds 0

# Custom tuning
pm collect-orderbooks --batch 25 --top-n 5 --loop-seconds 5.0
```

| Flag | Default (from .env) | Description |
|---|---|---|
| `--batch` | `DEFAULT_BATCH_SIZE` (50) | Tokens per request batch |
| `--top-n` | `DEFAULT_TOP_N` (10) | Top N bid/ask levels to store |
| `--loop-seconds` | `DEFAULT_LOOP_SECONDS` (2.0) | Sleep between full sweeps |
| `--per-batch-sleep` | `0.1` | Sleep between batches within a sweep |
| `--iterations` | `0` (forever) | Stop after N iterations |

Each iteration logs:

```
[collect] iter=1 ts=2026-03-10T12:00:00+00:00 inserted=42/50 fetched=50
```

If you see `[collect] no tracked tokens found`, check:

```sql
SELECT COUNT(*) FROM tracked_markets WHERE ended = false;
```

---

### 5. Refresh ended flags (optional, run periodically)

Marks `tracked_markets.ended = TRUE` for any market that is now closed, resolved, or past its `end_time`. This stops `collect-orderbooks` from polling expired markets.

```bash
pm refresh-ended
```

---

### 6. Export dataset

Exports orderbook feature rows to CSV, with optional corruption flagging.

```bash
pm export
```

With filters:

```bash
# Specific market
pm export --market-id 123456

# Specific token
pm export --token-id 0xabc...

# Time window
pm export --start 2026-03-01T00:00:00Z --end 2026-03-10T00:00:00Z

# Custom output files
pm export --out-clean my_data.csv --out-corrupted bad_rows.csv

# Flag rows where snapshot interval deviates from expected cadence
pm export --expected-seconds 2.0 --tolerance-seconds 0.5
```

| Flag | Default | Description |
|---|---|---|
| `--market-id` | none | Filter to one market |
| `--token-id` | none | Filter to one token |
| `--start` | none | ISO8601 start timestamp |
| `--end` | none | ISO8601 end timestamp |
| `--top-n-flatten` | `10` | Bid/ask levels to flatten into columns |
| `--expected-seconds` | none | Expected interval between snapshots |
| `--tolerance-seconds` | `0.5` | Allowed deviation from expected interval |
| `--out-clean` | `clean_orderbook_dataset.csv` | Output for clean rows |
| `--out-corrupted` | `flagged_corrupted_rows.csv` | Output for flagged rows |

Prints: `[export] clean_rows=18432 corrupted_rows=12`

---

## Typical full run

```bash
# 1. Apply schema (once)
pm migrate

# 2. Pull ~5000 active markets
pm ingest-markets --pages 5 --limit 1000

# 3. Auto-select top 100 liquid markets
pm auto-track --session run1 --top 100 --min-liquidity 5000

# 4. Collect continuously (run in a terminal/screen/tmux session)
pm collect-orderbooks --loop-seconds 2.0

# 5. Periodically expire ended markets
pm refresh-ended

# 6. Export
pm export --out-clean dataset.csv
```

---

## Useful diagnostic queries

```sql
-- Active markets available
SELECT COUNT(*)
FROM markets
WHERE COALESCE(is_closed, false) = false
  AND COALESCE(is_resolved, false) = false
  AND (end_time IS NULL OR end_time > NOW());

-- Tracked markets still active
SELECT COUNT(*) FROM tracked_markets WHERE ended = false;

-- Latest snapshot per token
SELECT DISTINCT ON (token_id)
  token_id, ts_utc, best_bid_price, best_ask_price
FROM orderbook_snapshots
ORDER BY token_id, ts_utc DESC;

-- Reset all data (destructive)
TRUNCATE TABLE features_orderbook, orderbook_snapshots, tracked_markets, markets CASCADE;
```

---

## Database schema

```
markets
  market_id PK, event_id, slug, question, condition_id,
  end_time, is_closed, is_resolved, is_active, category,
  volume_num, liquidity_num, updated_at, raw_json (JSONB)

tracked_markets
  market_id PK → markets.market_id
  sessions TEXT[], ended BOOL, first_seen_at, last_seen_at, ended_at

orderbook_snapshots
  (token_id, ts_utc) PK
  market_id → markets.market_id
  best_bid_price, best_bid_size, best_ask_price, best_ask_size
  bids_top_n_json, asks_top_n_json, raw_book_json

features_orderbook
  (token_id, ts_utc) PK → orderbook_snapshots
  spread, mid, microprice, imbalance_l1
  bid_depth_top_n, ask_depth_top_n
  seconds_to_expiry, hours_to_expiry
  extra_features_json (JSONB — top-5 depth metrics etc.)
```

---

## All commands at a glance

```
pm migrate                Apply SQL migrations
pm ingest-markets         Fetch market metadata from Gamma API
pm auto-track             Auto-select and track markets by policy
pm track-markets          Manually track specific market IDs
pm refresh-ended          Mark ended/closed markets in tracked_markets
pm collect-orderbooks     Poll CLOB API, store snapshots + features
pm export                 Export dataset to CSV
```

Run `pm <command> --help` for the full flag list on any command.
