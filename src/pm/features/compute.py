from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Features:
    spread: Optional[float]
    mid: Optional[float]
    microprice: Optional[float]
    imbalance_l1: Optional[float]
    bid_depth_top_n: Optional[float]
    ask_depth_top_n: Optional[float]
    seconds_to_expiry: Optional[float]
    hours_to_expiry: Optional[float]
    extra: Dict[str, Any]


def compute_features(
    ts: datetime,
    end_time: Optional[datetime],
    best_bid_price: Optional[float],
    best_bid_size: Optional[float],
    best_ask_price: Optional[float],
    best_ask_size: Optional[float],
    bids_top: List[List[float]],
    asks_top: List[List[float]],
) -> Features:
    spread = None
    mid = None
    microprice = None
    imbalance = None

    if best_bid_price is not None and best_ask_price is not None:
        spread = best_ask_price - best_bid_price
        mid = (best_ask_price + best_bid_price) / 2.0

        if best_bid_size is not None and best_ask_size is not None:
            denom = best_bid_size + best_ask_size
            if denom and denom > 0:
                microprice = (best_ask_price * best_bid_size + best_bid_price * best_ask_size) / denom
                imbalance = (best_bid_size - best_ask_size) / denom

    bid_depth = sum(x[1] for x in bids_top) if bids_top else None
    ask_depth = sum(x[1] for x in asks_top) if asks_top else None

    seconds_to_expiry = None
    hours_to_expiry = None
    if end_time is not None:
        seconds_to_expiry = (end_time - ts).total_seconds()
        hours_to_expiry = seconds_to_expiry / 3600.0

    return Features(
        spread=spread,
        mid=mid,
        microprice=microprice,
        imbalance_l1=imbalance,
        bid_depth_top_n=bid_depth,
        ask_depth_top_n=ask_depth,
        seconds_to_expiry=seconds_to_expiry,
        hours_to_expiry=hours_to_expiry,
        extra={},
    )