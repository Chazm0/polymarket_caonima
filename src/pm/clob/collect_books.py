from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, str) and not x.strip():
            return None
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except Exception:
        return None


def normalize_levels(levels: Any, top_n: int) -> List[List[float]]:
    out: List[List[float]] = []
    if not isinstance(levels, list):
        return out
    for item in levels[: max(0, top_n)]:
        px = None
        sz = None
        if isinstance(item, dict):
            px = _safe_float(item.get("price"))
            sz = _safe_float(item.get("size"))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            px = _safe_float(item[0])
            sz = _safe_float(item[1])
        if px is None or sz is None:
            continue
        out.append([px, sz])
    return out


def best_from_levels(bids: List[List[float]], asks: List[List[float]]) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    best_bid_px = bids[0][0] if bids else None
    best_bid_sz = bids[0][1] if bids else None
    best_ask_px = asks[0][0] if asks else None
    best_ask_sz = asks[0][1] if asks else None
    return best_bid_px, best_bid_sz, best_ask_px, best_ask_sz


@dataclass(frozen=True)
class Snapshot:
    token_id: str
    bids_top: List[List[float]]
    asks_top: List[List[float]]
    best_bid_price: Optional[float]
    best_bid_size: Optional[float]
    best_ask_price: Optional[float]
    best_ask_size: Optional[float]
    raw_book: Dict[str, Any]


def snapshot_from_book(token_id: str, book: Dict[str, Any], top_n: int) -> Snapshot:
    bids = normalize_levels(book.get("bids"), top_n)
    asks = normalize_levels(book.get("asks"), top_n)
    bbp, bbs, bap, bas = best_from_levels(bids, asks)
    return Snapshot(
        token_id=token_id,
        bids_top=bids,
        asks_top=asks,
        best_bid_price=bbp,
        best_bid_size=bbs,
        best_ask_price=bap,
        best_ask_size=bas,
        raw_book=book,
    )