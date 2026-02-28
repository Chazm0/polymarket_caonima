from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


@dataclass
class GammaClient:
    base: str
    user_agent: str = "polymarket-pipeline/0.1.0"
    timeout_s: int = 30
    retries: int = 3
    backoff_s: float = 0.7

    def __post_init__(self):
        self.base = self.base.rstrip("/")
        self.sess = requests.Session()
        self.sess.headers.update({"User-Agent": self.user_agent})

    def _get(self, path: str, params: Optional[dict] = None) -> Any:
        url = f"{self.base}{path}"
        last = None
        for i in range(self.retries):
            try:
                r = self.sess.get(url, params=params, timeout=self.timeout_s)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                last = e
                time.sleep(self.backoff_s * (2**i))
        raise last  # type: ignore

    def event_by_slug(self, slug: str) -> Dict[str, Any]:
        return self._get(f"/events/slug/{slug}")

    def list_markets(self, *, event_id: Optional[int] = None, limit: int = 1000, offset: int = 0) -> Any:
        params = {"limit": limit, "offset": offset}
        if event_id is not None:
            params["event_id"] = event_id
        return self._get("/markets", params=params)

    def market_by_id(self, market_id: int) -> Dict[str, Any]:
        return self._get(f"/markets/{market_id}")