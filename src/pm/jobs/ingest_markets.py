from __future__ import annotations

from typing import Any, Dict, List, Optional

from pm.db import DB
from pm.gamma.client import GammaClient
from pm.gamma.ingest import upsert_markets


def _normalize_markets_payload(payload: Any) -> List[Dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("markets"), list):
        return [x for x in payload["markets"] if isinstance(x, dict)]
    return []


def ingest_markets(
    *,
    db: DB,
    gamma: GammaClient,
    event_id: Optional[int] = None,
    limit: int = 1000,
    pages: int = 1,
) -> int:
    total = 0
    offset = 0
    for _ in range(max(1, pages)):
        payload = gamma.list_markets(event_id=event_id, limit=limit, offset=offset)
        markets = _normalize_markets_payload(payload)
        if not markets:
            break
        total += upsert_markets(db, markets)
        offset += limit
    return total