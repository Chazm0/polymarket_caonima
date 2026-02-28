from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from psycopg.types.json import Json
from pm.db import DB
from datetime import timedelta

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, str) and not x.strip():
            return None
        return float(x)
    except Exception:
        return None


def normalize_market(m: Dict[str, Any]) -> Dict[str, Any]:
    market_id = m.get("id") or m.get("market_id") or m.get("marketId")
    if market_id is None:
        raise RuntimeError("Market missing id")

    end_time = (
        _parse_iso(m.get("endTime"))
        or _parse_iso(m.get("end_time"))
        or _parse_iso(m.get("endDate"))
        or _parse_iso(m.get("end_date"))
    )

    return {
        "market_id": int(market_id),
        "event_id": m.get("eventId") or m.get("event_id"),
        "slug": m.get("slug"),
        "question": m.get("question") or m.get("title"),
        "condition_id": m.get("conditionId") or m.get("condition_id"),
        "end_time": end_time,
        "is_closed": m.get("closed") if isinstance(m.get("closed"), bool) else m.get("isClosed"),
        "is_resolved": m.get("resolved") if isinstance(m.get("resolved"), bool) else m.get("isResolved"),
        "is_active": m.get("active") if isinstance(m.get("active"), bool) else m.get("isActive"),
        "category": m.get("category"),
        "volume_num": _safe_float(m.get("volume") or m.get("volumeNum") or m.get("volume_num")),
        "liquidity_num": _safe_float(m.get("liquidity") or m.get("liquidityNum") or m.get("liquidity_num")),
    }


UPSERT_SQL = """
INSERT INTO markets (
  market_id, event_id, slug, question, condition_id, end_time,
  is_closed, is_resolved, is_active, category, volume_num, liquidity_num,
  updated_at, raw_json
)
VALUES (
  %s,%s,%s,%s,%s,%s,
  %s,%s,%s,%s,%s,%s,
  %s,%s
)
ON CONFLICT (market_id) DO UPDATE SET
  event_id      = EXCLUDED.event_id,
  slug          = EXCLUDED.slug,
  question      = EXCLUDED.question,
  condition_id  = EXCLUDED.condition_id,
  end_time      = EXCLUDED.end_time,
  is_closed     = EXCLUDED.is_closed,
  is_resolved   = EXCLUDED.is_resolved,
  is_active     = EXCLUDED.is_active,
  category      = EXCLUDED.category,
  volume_num    = EXCLUDED.volume_num,
  liquidity_num = EXCLUDED.liquidity_num,
  updated_at    = EXCLUDED.updated_at,
  raw_json      = EXCLUDED.raw_json
"""


def upsert_markets(db: DB, markets: List[Dict[str, Any]]) -> int:
    ts = _now_utc()
    n = 0
    with db.connection() as conn:
        with conn.cursor() as cur:
            for m in markets:
                nm = normalize_market(m)
                
                now = _now_utc()
                end_time = nm["end_time"]

                # Skip clearly stale markets (tune window as desired)
                if end_time is not None and end_time < (now - timedelta(days=30)):
                    continue

                # Skip closed/resolved if those flags exist
                if nm["is_closed"] is True or nm["is_resolved"] is True:
                    continue
                cur.execute(
                    UPSERT_SQL,
                    (
                        nm["market_id"],
                        nm["event_id"],
                        nm["slug"],
                        nm["question"],
                        nm["condition_id"],
                        nm["end_time"],
                        nm["is_closed"],
                        nm["is_resolved"],
                        nm["is_active"],
                        nm["category"],
                        nm["volume_num"],
                        nm["liquidity_num"],
                        ts,
                        Json(m),
                    ),
                )
                n += 1
        conn.commit()
    return n


def extract_token_ids(market_raw: Dict[str, Any]) -> List[str]:
    out: List[str] = []

    v = market_raw.get("clobTokenIds")
    if isinstance(v, list):
        out.extend([str(x) for x in v if x is not None])

    v2 = market_raw.get("clobTokenId")
    if v2 is not None:
        out.append(str(v2))

    for key in ("outcomes", "outcomeTokens", "tokens"):
        vv = market_raw.get(key)
        if isinstance(vv, list):
            for item in vv:
                if isinstance(item, dict):
                    tid = item.get("tokenId") or item.get("clobTokenId") or item.get("id")
                    if tid is not None:
                        out.append(str(tid))

    # dedup preserve order
    seen = set()
    deduped = []
    for t in out:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped