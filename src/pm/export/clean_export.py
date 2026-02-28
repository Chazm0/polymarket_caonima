from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import pandas as pd
from sqlalchemy import create_engine, text

from pm.export.corruption_checks import CorruptionConfig, cadence_flags


ALIGNED_SQL = """
WITH s AS (
  SELECT token_id, market_id, ts_utc,
         best_bid_price, best_bid_size, best_ask_price, best_ask_size,
         bids_top_n_json, asks_top_n_json
  FROM orderbook_snapshots
  WHERE (:market_id IS NULL OR market_id = :market_id)
    AND (:token_id IS NULL OR token_id = :token_id)
    AND (:start_ts IS NULL OR ts_utc >= :start_ts)
    AND (:end_ts   IS NULL OR ts_utc <= :end_ts)
),
f AS (
  SELECT token_id, market_id AS feat_market_id, ts_utc,
         spread, mid, microprice, imbalance_l1,
         bid_depth_top_n, ask_depth_top_n,
         seconds_to_expiry, hours_to_expiry,
         extra_features_json
  FROM features_orderbook
  WHERE (:market_id IS NULL OR market_id = :market_id)
    AND (:token_id IS NULL OR token_id = :token_id)
    AND (:start_ts IS NULL OR ts_utc >= :start_ts)
    AND (:end_ts   IS NULL OR ts_utc <= :end_ts)
)
SELECT
  s.token_id,
  COALESCE(s.market_id, f.feat_market_id) AS market_id,
  s.ts_utc,
  s.best_bid_price, s.best_bid_size, s.best_ask_price, s.best_ask_size,
  s.bids_top_n_json, s.asks_top_n_json,
  f.spread, f.mid, f.microprice, f.imbalance_l1,
  f.bid_depth_top_n, f.ask_depth_top_n,
  f.seconds_to_expiry, f.hours_to_expiry,
  f.extra_features_json
FROM s
JOIN f USING (token_id, ts_utc)
ORDER BY s.token_id, s.ts_utc
"""

ORPHANS_SQL = """
WITH s AS (
  SELECT token_id, ts_utc
  FROM orderbook_snapshots
  WHERE (:market_id IS NULL OR market_id = :market_id)
    AND (:token_id IS NULL OR token_id = :token_id)
    AND (:start_ts IS NULL OR ts_utc >= :start_ts)
    AND (:end_ts   IS NULL OR ts_utc <= :end_ts)
),
f AS (
  SELECT token_id, ts_utc
  FROM features_orderbook
  WHERE (:market_id IS NULL OR market_id = :market_id)
    AND (:token_id IS NULL OR token_id = :token_id)
    AND (:start_ts IS NULL OR ts_utc >= :start_ts)
    AND (:end_ts   IS NULL OR ts_utc <= :end_ts)
)
SELECT token_id, ts_utc, 'snapshot_without_features' AS reason
FROM s
LEFT JOIN f USING (token_id, ts_utc)
WHERE f.token_id IS NULL
UNION ALL
SELECT token_id, ts_utc, 'features_without_snapshot' AS reason
FROM f
LEFT JOIN s USING (token_id, ts_utc)
WHERE s.token_id IS NULL
ORDER BY token_id, ts_utc
"""


def _ensure_levels(v: Any) -> list[list[float]]:
    if v is None:
        return []
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            return []
    if not isinstance(v, list):
        return []
    out = []
    for item in v:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            try:
                out.append([float(item[0]), float(item[1])])
            except Exception:
                pass
        elif isinstance(item, dict):
            try:
                out.append([float(item.get("price")), float(item.get("size"))])
            except Exception:
                pass
    return out


def flatten_top_levels(df: pd.DataFrame, top_n: int) -> pd.DataFrame:
    if top_n <= 0 or df.empty:
        return df

    for i in range(1, top_n + 1):
        df[f"bid_px_{i}"] = pd.NA
        df[f"bid_sz_{i}"] = pd.NA
        df[f"ask_px_{i}"] = pd.NA
        df[f"ask_sz_{i}"] = pd.NA

    for idx, row in df.iterrows():
        bids = _ensure_levels(row.get("bids_top_n_json"))
        asks = _ensure_levels(row.get("asks_top_n_json"))
        for i in range(top_n):
            if i < len(bids):
                df.at[idx, f"bid_px_{i+1}"] = bids[i][0]
                df.at[idx, f"bid_sz_{i+1}"] = bids[i][1]
            if i < len(asks):
                df.at[idx, f"ask_px_{i+1}"] = asks[i][0]
                df.at[idx, f"ask_sz_{i+1}"] = asks[i][1]
    return df


@dataclass(frozen=True)
class ExportParams:
    dsn: str
    market_id: Optional[int] = None
    token_id: Optional[str] = None
    start_ts: Optional[datetime] = None
    end_ts: Optional[datetime] = None
    top_n_flatten: int = 10
    corruption: CorruptionConfig = CorruptionConfig()
    out_clean: str = "clean_orderbook_dataset.csv"
    out_corrupted: str = "flagged_corrupted_rows.csv"


def export_dataset(params: ExportParams) -> tuple[int, int]:
    engine = create_engine(params.dsn)

    qparams = {
        "market_id": params.market_id,
        "token_id": params.token_id,
        "start_ts": params.start_ts,
        "end_ts": params.end_ts,
    }

    aligned = pd.read_sql_query(text(ALIGNED_SQL), engine, params=qparams, parse_dates=["ts_utc"])
    orphans = pd.read_sql_query(text(ORPHANS_SQL), engine, params=qparams, parse_dates=["ts_utc"])

    cadence_bad = cadence_flags(aligned, params.corruption)

    corrupted = pd.concat([orphans, cadence_bad], ignore_index=True)
    if not corrupted.empty:
        corrupted = corrupted.drop_duplicates(subset=["token_id", "ts_utc", "reason"]).sort_values(["token_id", "ts_utc", "reason"])

    if not corrupted.empty and not aligned.empty:
        bad_keys = corrupted[["token_id", "ts_utc"]].drop_duplicates()
        aligned = aligned.merge(bad_keys.assign(_bad=1), on=["token_id", "ts_utc"], how="left")
        clean = aligned[aligned["_bad"].isna()].drop(columns=["_bad"])
    else:
        clean = aligned

    clean = flatten_top_levels(clean, params.top_n_flatten)

    clean.to_csv(params.out_clean, index=False)
    corrupted.to_csv(params.out_corrupted, index=False)

    return len(clean), len(corrupted)