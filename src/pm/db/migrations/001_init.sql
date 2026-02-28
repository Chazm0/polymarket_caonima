BEGIN;

CREATE TABLE IF NOT EXISTS markets (
  market_id        BIGINT PRIMARY KEY,
  event_id         BIGINT,
  slug             TEXT,
  question         TEXT,
  condition_id     TEXT,
  end_time         TIMESTAMPTZ,
  is_closed        BOOLEAN,
  is_resolved      BOOLEAN,
  is_active        BOOLEAN,
  category         TEXT,
  volume_num       DOUBLE PRECISION,
  liquidity_num    DOUBLE PRECISION,
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  raw_json         JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS tracked_markets (
  market_id      BIGINT PRIMARY KEY REFERENCES markets(market_id) ON DELETE CASCADE,
  sessions       TEXT[] NOT NULL DEFAULT '{}',
  ended          BOOLEAN NOT NULL DEFAULT FALSE,
  first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ended_at       TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS orderbook_snapshots (
  token_id          TEXT NOT NULL,
  market_id         BIGINT REFERENCES markets(market_id) ON DELETE SET NULL,
  ts_utc            TIMESTAMPTZ NOT NULL,
  best_bid_price    DOUBLE PRECISION,
  best_bid_size     DOUBLE PRECISION,
  best_ask_price    DOUBLE PRECISION,
  best_ask_size     DOUBLE PRECISION,
  bids_top_n_json   JSONB,
  asks_top_n_json   JSONB,
  raw_book_json     JSONB,
  inserted_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT pk_orderbook_snapshots PRIMARY KEY (token_id, ts_utc)
);

CREATE TABLE IF NOT EXISTS features_orderbook (
  token_id             TEXT NOT NULL,
  market_id            BIGINT REFERENCES markets(market_id) ON DELETE SET NULL,
  ts_utc               TIMESTAMPTZ NOT NULL,
  spread               DOUBLE PRECISION,
  mid                  DOUBLE PRECISION,
  microprice           DOUBLE PRECISION,
  imbalance_l1         DOUBLE PRECISION,
  bid_depth_top_n      DOUBLE PRECISION,
  ask_depth_top_n      DOUBLE PRECISION,
  seconds_to_expiry    DOUBLE PRECISION,
  hours_to_expiry      DOUBLE PRECISION,
  extra_features_json  JSONB,
  inserted_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT pk_features_orderbook PRIMARY KEY (token_id, ts_utc),
  CONSTRAINT fk_features_snapshot
    FOREIGN KEY (token_id, ts_utc)
    REFERENCES orderbook_snapshots(token_id, ts_utc)
    ON DELETE CASCADE
);

COMMIT;