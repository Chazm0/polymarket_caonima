from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from pm.clob.client import ClobClient
from pm.clob.collect_books import snapshot_from_book
from pm.db import DB
from pm.features.jobs import insert_snapshot_and_features


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _chunks(xs: List[str], n: int):
    for i in range(0, len(xs), n):
        yield xs[i : i + n]


def _get_tracked_tokens_and_end_times(db: DB) -> Tuple[Dict[str, int], Dict[int, Optional[datetime]]]:
    """
    Returns:
      token_id -> market_id
      market_id -> end_time
    """
    token_to_market: Dict[str, int] = {}
    market_end: Dict[int, Optional[datetime]] = {}

    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT
                  tok.token_id AS token_id,
                  m.market_id  AS market_id,
                  m.end_time   AS end_time
                FROM tracked_markets t
                JOIN markets m ON m.market_id = t.market_id
                CROSS JOIN LATERAL (
                  SELECT jsonb_array_elements_text(
                           CASE
                             WHEN jsonb_typeof(m.raw_json->'clobTokenIds') = 'array'
                               THEN m.raw_json->'clobTokenIds'
                             WHEN jsonb_typeof(m.raw_json->'clobTokenIds') = 'string'
                               THEN (m.raw_json->>'clobTokenIds')::jsonb
                             ELSE '[]'::jsonb
                           END
                         ) AS token_id
                ) tok
                WHERE t.ended = false
                """
            )
            rows = cur.fetchall()

    for r in rows:
        tid = str(r["token_id"])
        mid = int(r["market_id"])
        token_to_market[tid] = mid
        market_end[mid] = r["end_time"]

    return token_to_market, market_end


def collect_orderbooks_loop(
    *,
    db: DB,
    clob: ClobClient,
    batch_size: int,
    top_n: int,
    loop_seconds: float,
    per_batch_sleep: float,
    iterations: int,  # 0=forever
) -> None:
    it = 0
    did_debug = False

    while True:
        it += 1
        ts = _now()

        token_to_market, market_end = _get_tracked_tokens_and_end_times(db)
        token_ids = list(token_to_market.keys())

        if not token_ids:
            print("[collect] no tracked tokens found; sleeping...")
            time.sleep(max(loop_seconds, 1.0))
            continue

        inserted = 0
        fetched = 0

        for chunk in _chunks(token_ids, max(1, batch_size)):
            # Fetch per token using GET /book (reliable in your environment)
            for tid in chunk:
                book = clob.book(tid)
                fetched += 1

                if not isinstance(book, dict) or not book:
                    continue

                # One-time debug to confirm shape
                if not did_debug:
                    print("[collect][debug] first book keys:", list(book.keys())[:25])
                    did_debug = True

                snap = snapshot_from_book(tid, book, top_n=top_n)
                if snap is None:
                    continue

                mid = token_to_market.get(tid)
                end_time = market_end.get(mid) if mid is not None else None

                insert_snapshot_and_features(db, market_id=mid, ts=ts, snapshot=snap, end_time=end_time)
                inserted += 1

            if per_batch_sleep > 0:
                time.sleep(per_batch_sleep)

        print(f"[collect] iter={it} ts={ts.isoformat()} inserted={inserted}/{len(token_ids)} fetched={fetched}")

        if iterations > 0 and it >= iterations:
            break
        if loop_seconds > 0:
            time.sleep(loop_seconds)