BEGIN;

CREATE INDEX IF NOT EXISTS idx_markets_event_id       ON markets (event_id);
CREATE INDEX IF NOT EXISTS idx_markets_end_time       ON markets (end_time);
CREATE INDEX IF NOT EXISTS idx_markets_updated_at     ON markets (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_markets_is_closed      ON markets (is_closed);
CREATE INDEX IF NOT EXISTS idx_markets_raw_json_gin   ON markets USING GIN (raw_json);

CREATE INDEX IF NOT EXISTS idx_tracked_ended          ON tracked_markets (ended);
CREATE INDEX IF NOT EXISTS idx_tracked_last_seen      ON tracked_markets (last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_tracked_sessions_gin   ON tracked_markets USING GIN (sessions);

CREATE INDEX IF NOT EXISTS idx_obs_market_ts          ON orderbook_snapshots (market_id, ts_utc DESC);
CREATE INDEX IF NOT EXISTS idx_obs_token_ts           ON orderbook_snapshots (token_id, ts_utc DESC);
CREATE INDEX IF NOT EXISTS idx_obs_ts                 ON orderbook_snapshots (ts_utc DESC);

CREATE INDEX IF NOT EXISTS idx_feat_market_ts         ON features_orderbook (market_id, ts_utc DESC);
CREATE INDEX IF NOT EXISTS idx_feat_token_ts          ON features_orderbook (token_id, ts_utc DESC);
CREATE INDEX IF NOT EXISTS idx_feat_ts                ON features_orderbook (ts_utc DESC);
CREATE INDEX IF NOT EXISTS idx_feat_extra_gin         ON features_orderbook USING GIN (extra_features_json);

COMMIT;