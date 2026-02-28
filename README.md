Polymarket Postgres Pipeline

A Postgres-first microstructure data pipeline for:

Ingesting markets from Gamma

Selecting markets via manual tracking or Auto-Tracker

Collecting CLOB orderbooks

Computing advanced orderbook features

Exporting modeling-ready datasets

Architecture Overview
Gamma API  →  markets
                 ↓
           tracked_markets  ← (manual + auto-tracker)
                 ↓
          orderbook_snapshots  ← CLOB /book endpoint
                 ↓
           features_orderbook
                 ↓
               export
Tables
Table	Purpose
markets	Canonical Gamma market metadata
tracked_markets	Controls which markets are collected
orderbook_snapshots	Raw time-series orderbook data
features_orderbook	Derived microstructure features
schema_migrations	Migration tracking
Feature Engineering (NEW)

Each snapshot now computes:

Level 1

spread

mid = (best_bid + best_ask)/2

microprice = (ask * bid_size + bid * ask_size) / (bid_size + ask_size)

imbalance_l1

Top-N (default N=30)

bid_depth_top_n

ask_depth_top_n

Top-5 Depth Metrics (NEW)

depth_bid_top5

depth_ask_top5

imbalance_top5 = (depth_bid_top5 - depth_ask_top5) / (depth_bid_top5 + depth_ask_top5)

1️⃣ Requirements

Python 3.11+

Postgres (Neon recommended)

Internet access to:

https://gamma-api.polymarket.com

https://clob.polymarket.com

2️⃣ Setup

From repo root:

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .

Verify CLI:

pm --help
3️⃣ Configure .env

Example (Neon):

DATABASE_DSN_PG=postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require
GAMMA_BASE=https://gamma-api.polymarket.com
CLOB_BASE=https://clob.polymarket.com
USER_AGENT=pm-pipeline/0.1
STATEMENT_TIMEOUT_MS=60000
DEFAULT_BATCH_SIZE=20
DEFAULT_TOP_N=30
DEFAULT_LOOP_SECONDS=2.0

⚠️ If you see:

getaddrinfo ENOTFOUND HOST

You left HOST as a placeholder. Replace with your actual Neon hostname.

4️⃣ Apply Migrations
pm migrate
5️⃣ Reset Database (if needed)
TRUNCATE TABLE
  features_orderbook,
  orderbook_snapshots,
  tracked_markets,
  markets
CASCADE;

Why CASCADE?
Postgres blocks truncating referenced tables otherwise.

6️⃣ Ingest Markets
pm ingest-markets --pages 5 --limit 1000

Verify:

SELECT COUNT(*) AS n, MAX(end_time) FROM markets;
7️⃣ Track Markets
Manual
pm track-markets --session manual --market-ids 123,456
Auto-Tracker

Track high liquidity:

pm auto-track --session hot --top 200 --min-liquidity 5000

Track markets ending soon:

pm auto-track --session ending_24h --top 200 --ends-within-hours 24

Dry run:

pm auto-track --session hot --top 50 --dry-run
8️⃣ Refresh Expired Markets
pm refresh-ended
9️⃣ Collect Orderbooks

Now uses:

GET /book?token_id=...

Example:

pm collect-orderbooks --iterations 3

Continuous mode:

pm collect-orderbooks

Custom:

pm collect-orderbooks --batch 10 --top-n 30 --loop-seconds 2

If you see:

[collect] no tracked tokens found

Check:

SELECT COUNT(*) FROM tracked_markets WHERE ended=false;
🔟 Export Dataset
pm export --market-id 123 --expected-seconds 2

With time window:

pm export --market-id 123 --start 2026-02-28T00:00:00Z --end 2026-02-28T06:00:00Z

Outputs:

clean_orderbook_dataset.csv

flagged_corrupted_rows.csv

11️⃣ VS Code Setup (IMPORTANT)
Required Extensions

Install these from VS Code Extensions panel:

1️⃣ SQLTools

Publisher: mtxr

2️⃣ SQLTools PostgreSQL Driver

Publisher: mtxr

How to Install

Open VS Code

Press Ctrl + Shift + X

Search:

SQLTools

Install

Search:

SQLTools PostgreSQL

Install

Restart VS Code after installing.

Create Neon Connection

Open Command Palette (Ctrl + Shift + P)

Run:

SQLTools: Add New Connection

Select:

PostgreSQL

Fill:

Host → your Neon host

Port → 5432

Database → your DB name

Username → your Neon user

Password → your Neon password

SSL → Enabled

Save.

Common SQLTools Errors
❌ Cannot read properties of null (reading 'driver')

Fix:

Delete broken connection from settings.json

Recreate connection

Ensure driver = "PostgreSQL"

❌ getaddrinfo ENOTFOUND HOST

You left HOST as literal text. Replace with real hostname.

12️⃣ Useful SQL Diagnostics

Active markets:

SELECT COUNT(*)
FROM markets
WHERE COALESCE(is_closed,false)=false
  AND COALESCE(is_resolved,false)=false
  AND (end_time IS NULL OR end_time > NOW());

Tracked active:

SELECT COUNT(*) FROM tracked_markets WHERE ended=false;

Latest snapshot per token:

SELECT DISTINCT ON (token_id)
  token_id, ts_utc, best_bid_price, best_ask_price
FROM orderbook_snapshots
ORDER BY token_id, ts_utc DESC;
13️⃣ Virtual Environment

Why .venv?

Isolates psycopg, requests, pandas

Prevents version conflicts

Required for reproducibility

Activate:

.\.venv\Scripts\Activate.ps1

If PowerShell blocks activation:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
14️⃣ Typical End-to-End Flow
pm migrate
pm ingest-markets --pages 10
pm auto-track --session hot --top 200 --allow-missing-token-keys
pm collect-orderbooks --iterations 10
pm export --market-id <id> --expected-seconds 2
Design Philosophy

Postgres is the single source of truth

tracked_markets gates collection

Orderbook features computed inline

Export produces modeling-ready data

Future Improvements

Normalize tokens into market_tokens

Async CLOB requests

Feature versioning

Docker deployment

Materialized feature views

Real-time streaming collector