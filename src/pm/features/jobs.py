from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, Dict, List

from psycopg.types.json import Json

from pm.clob.collect_books import Snapshot
from pm.db import DB
from pm.features.compute import compute_features


SNAPSHOT_INSERT_SQL = """
INSERT INTO orderbook_snapshots (
  token_id, market_id, ts_utc,
  best_bid_price, best_bid_size, best_ask_price, best_ask_size,
  bids_top_n_json, asks_top_n_json, raw_book_json, inserted_at
)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON CONFLICT (token_id, ts_utc) DO NOTHING
"""

FEATURE_UPSERT_SQL = """
INSERT INTO features_orderbook (
  token_id, market_id, ts_utc,
  spread, mid, microprice, imbalance_l1,
  bid_depth_top_n, ask_depth_top_n,
  depth_bid_top5, depth_ask_top5, imbalance_top5,
  seconds_to_expiry, hours_to_expiry,
  extra_features_json, inserted_at
)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON CONFLICT (token_id, ts_utc) DO UPDATE SET
  market_id           = EXCLUDED.market_id,
  spread              = EXCLUDED.spread,
  mid                 = EXCLUDED.mid,
  microprice          = EXCLUDED.microprice,
  imbalance_l1        = EXCLUDED.imbalance_l1,
  bid_depth_top_n     = EXCLUDED.bid_depth_top_n,
  ask_depth_top_n     = EXCLUDED.ask_depth_top_n,
  depth_bid_top5      = EXCLUDED.depth_bid_top5,
  depth_ask_top5      = EXCLUDED.depth_ask_top5,
  imbalance_top5      = EXCLUDED.imbalance_top5,
  seconds_to_expiry   = EXCLUDED.seconds_to_expiry,
  hours_to_expiry     = EXCLUDED.hours_to_expiry,
  extra_features_json = EXCLUDED.extra_features_json,
  inserted_at         = EXCLUDED.inserted_at
"""


def _sum_top_levels(levels: Any, n: int) -> float:
    """
    levels: list of dicts like {"price": float, "size": float}
    """
    if not isinstance(levels, list):
        return 0.0
    s = 0.0
    for x in levels[:n]:
        if not isinstance(x, dict):
            continue
        try:
            s += float(x.get("size") or 0.0)
        except Exception:
            pass
    return s


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def insert_snapshot_and_features(
    db: DB,
    *,
    market_id: Optional[int],
    ts: datetime,
    snapshot: Snapshot,
    end_time: Optional[datetime],
) -> None:
    # Keep using your existing feature computation (spread, imbalance_l1, expiry, etc.)
    feats = compute_features(
        ts=ts,
        end_time=end_time,
        best_bid_price=snapshot.best_bid_price,
        best_bid_size=snapshot.best_bid_size,
        best_ask_price=snapshot.best_ask_price,
        best_ask_size=snapshot.best_ask_size,
        bids_top=snapshot.bids_top,
        asks_top=snapshot.asks_top,
    )

    # --- New requested attributes (calculated from snapshot) ---
    bid = _safe_float(snapshot.best_bid_price)
    ask = _safe_float(snapshot.best_ask_price)
    bid_sz = _safe_float(snapshot.best_bid_size)
    ask_sz = _safe_float(snapshot.best_ask_size)

    # mid price = (best bid + best ask) / 2
    mid = None
    if bid is not None and ask is not None:
        mid = (bid + ask) / 2.0

    # microprice = (ask * bid_size + bid * ask_size) / (bid_size + ask_size)
    microprice = None
    if bid is not None and ask is not None and bid_sz is not None and ask_sz is not None:
        denom = bid_sz + ask_sz
        if denom > 0:
            microprice = (ask * bid_sz + bid * ask_sz) / denom

    # depth_bid_top5 / depth_ask_top5
    depth_bid_top5 = _sum_top_levels(snapshot.bids_top, 5)
    depth_ask_top5 = _sum_top_levels(snapshot.asks_top, 5)

    # imbalance_top5 = (db - da) / (db + da)
    imbalance_top5 = None
    denom = depth_bid_top5 + depth_ask_top5
    if denom > 0:
        imbalance_top5 = (depth_bid_top5 - depth_ask_top5) / denom

    # Optionally also stash them in extra_features_json for convenience/back-compat
    extra: Dict[str, Any] = dict(feats.extra or {})
    extra.update(
        {
            "depth_bid_top5": depth_bid_top5,
            "depth_ask_top5": depth_ask_top5,
            "imbalance_top5": imbalance_top5,
        }
    )

    with db.connection() as conn:
        with conn.cursor() as cur:
            # snapshots table (top-N levels are already stored)
            cur.execute(
                SNAPSHOT_INSERT_SQL,
                (
                    snapshot.token_id,
                    market_id,
                    ts,
                    snapshot.best_bid_price,
                    snapshot.best_bid_size,
                    snapshot.best_ask_price,
                    snapshot.best_ask_size,
                    Json(snapshot.bids_top),
                    Json(snapshot.asks_top),
                    Json(snapshot.raw_book),
                    ts,
                ),
            )

            # features table (use computed mid/microprice to match your formulas)
            cur.execute(
                FEATURE_UPSERT_SQL,
                (
                    snapshot.token_id,
                    market_id,
                    ts,
                    feats.spread,
                    mid,
                    microprice,
                    feats.imbalance_l1,
                    feats.bid_depth_top_n,
                    feats.ask_depth_top_n,
                    depth_bid_top5,
                    depth_ask_top5,
                    imbalance_top5,
                    feats.seconds_to_expiry,
                    feats.hours_to_expiry,
                    Json(extra),
                    ts,
                ),
            )
        conn.commit()