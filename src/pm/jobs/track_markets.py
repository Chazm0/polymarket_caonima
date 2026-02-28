from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple

from pm.db import DB


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# -----------------------
# Manual tracking (existing behavior)
# -----------------------
def track_markets(*, db: DB, market_ids: List[int], session: str) -> int:
    """
    Insert markets into tracked_markets and attach a session tag.
    Idempotent: adds session to sessions[] if not already present.
    """
    if not market_ids:
        return 0

    ts = _now_utc()

    sql = """
    INSERT INTO tracked_markets (market_id, sessions, ended, first_seen_at, last_seen_at)
    VALUES (%s, ARRAY[%s], FALSE, %s, %s)
    ON CONFLICT (market_id) DO UPDATE SET
      sessions = (
        SELECT ARRAY(SELECT DISTINCT unnest(tracked_markets.sessions || EXCLUDED.sessions))
      ),
      ended = FALSE,
      last_seen_at = EXCLUDED.last_seen_at
    """

    with db.connection() as conn:
        with conn.cursor() as cur:
            for mid in market_ids:
                cur.execute(sql, (mid, session, ts, ts))
        conn.commit()

    return len(market_ids)


def refresh_ended_flags(db: DB) -> int:
    """
    Mark tracked markets ended when:
      - markets.is_closed = true OR
      - markets.is_resolved = true OR
      - markets.end_time <= now()
    """
    ts = _now_utc()
    sql = """
    UPDATE tracked_markets tm
    SET ended = TRUE,
        ended_at = COALESCE(tm.ended_at, %s)
    FROM markets m
    WHERE tm.market_id = m.market_id
      AND tm.ended = FALSE
      AND (
        COALESCE(m.is_closed, FALSE) = TRUE
        OR COALESCE(m.is_resolved, FALSE) = TRUE
        OR (m.end_time IS NOT NULL AND m.end_time <= %s)
      )
    """

    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (ts, ts))
            n = cur.rowcount
        conn.commit()

    return int(n)


# -----------------------
# Auto-tracker (new)
# -----------------------
@dataclass(frozen=True)
class AutoTrackPolicy:
    session: str
    top_n: int = 200

    # selection filters
    min_liquidity: Optional[float] = None
    min_volume: Optional[float] = None
    ends_within_hours: Optional[float] = None     # only markets ending soon
    category: Optional[str] = None

    # lifecycle controls
    include_closed: bool = False                  # usually False
    include_already_tracked: bool = False         # default: only new markets
    require_token_keys: bool = True               # require raw_json has clobTokenIds or clobTokenId


def auto_track_markets(
    *,
    db: DB,
    policy: AutoTrackPolicy,
    dry_run: bool = False,
) -> Tuple[int, List[int]]:
    """
    Auto-select markets from markets and insert them into tracked_markets.

    Returns:
      (tracked_count, selected_market_ids)

    Notes:
    - token availability: we can only cheaply check for presence of token keys in raw_json
      via JSONB operator '?'. This does NOT guarantee the token IDs are valid, but it prevents
      the obvious "no tokens at all" situation.
    """
    if policy.top_n <= 0:
        return (0, [])

    now = _now_utc()
    end_cutoff = None
    if policy.ends_within_hours is not None:
        end_cutoff = now + timedelta(hours=float(policy.ends_within_hours))

    where = []
    params = {"now": now, "end_cutoff": end_cutoff, "category": policy.category}

    # Exclude ended markets by default
    if not policy.include_closed:
        where.append("COALESCE(m.is_closed, FALSE) = FALSE")
        where.append("COALESCE(m.is_resolved, FALSE) = FALSE")
        where.append("COALESCE(m.is_active, TRUE) = TRUE")
        where.append("(m.end_time IS NULL OR m.end_time > %(now)s)")

    # Ending soon filter
    if end_cutoff is not None:
        where.append("(m.end_time IS NOT NULL AND m.end_time <= %(end_cutoff)s)")

    # numeric filters
    if policy.min_liquidity is not None:
        where.append("(m.liquidity_num IS NOT NULL AND m.liquidity_num >= %(min_liquidity)s)")
        params["min_liquidity"] = float(policy.min_liquidity)

    if policy.min_volume is not None:
        where.append("(m.volume_num IS NOT NULL AND m.volume_num >= %(min_volume)s)")
        params["min_volume"] = float(policy.min_volume)

    if policy.category is not None:
        where.append("(m.category = %(category)s)")

    # Token keys present in raw_json (cheap guardrail)
    if policy.require_token_keys:
        where.append("((m.raw_json ? 'clobTokenIds') OR (m.raw_json ? 'clobTokenId'))")

    # Join against tracked_markets so we can skip already tracked (default)
    join_tm = "LEFT JOIN tracked_markets tm ON tm.market_id = m.market_id"
    if not policy.include_already_tracked:
        where.append("tm.market_id IS NULL")

    where_sql = " AND ".join(where) if where else "TRUE"

    # Rank by liquidity then volume then recency.
    # (This is a sane default “hot markets” heuristic.)
    select_sql = f"""
    SELECT m.market_id
    FROM markets m
    {join_tm}
    WHERE {where_sql}
    ORDER BY
      COALESCE(m.liquidity_num, 0) DESC,
      COALESCE(m.volume_num, 0) DESC,
      m.updated_at DESC
    LIMIT {int(policy.top_n)}
    """

    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(select_sql, params)
            rows = cur.fetchall()
            market_ids = [int(r["market_id"]) for r in rows]

    if dry_run or not market_ids:
        return (0, market_ids)

    # Upsert selected markets into tracked_markets (attach policy.session)
    ts = now
    upsert_sql = """
    INSERT INTO tracked_markets (market_id, sessions, ended, first_seen_at, last_seen_at)
    VALUES (%s, ARRAY[%s], FALSE, %s, %s)
    ON CONFLICT (market_id) DO UPDATE SET
      sessions = (
        SELECT ARRAY(SELECT DISTINCT unnest(tracked_markets.sessions || EXCLUDED.sessions))
      ),
      ended = FALSE,
      last_seen_at = EXCLUDED.last_seen_at
    """

    with db.connection() as conn:
        with conn.cursor() as cur:
            for mid in market_ids:
                cur.execute(upsert_sql, (mid, policy.session, ts, ts))
        conn.commit()

    return (len(market_ids), market_ids)