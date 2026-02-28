from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


@dataclass
class ClobClient:
    base: str
    user_agent: str = "polymarket-pipeline/0.1.0"
    timeout_s: int = 30
    retries: int = 3
    backoff_s: float = 0.7

    def __post_init__(self):
        self.base = self.base.rstrip("/")
        self.sess = requests.Session()
        self.sess.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            }
        )

    def book(self, token_id: str) -> Dict[str, Any]:
        """
        Fetch a single orderbook.

        Proven working in your environment:
          GET https://clob.polymarket.com/book?token_id=...

        Returns an object (dict). If the token is unknown/empty, may return {}.
        """
        url = f"{self.base}/book"
        last: Optional[Exception] = None

        for i in range(self.retries):
            try:
                r = self.sess.get(url, params={"token_id": str(token_id)}, timeout=self.timeout_s)
                r.raise_for_status()
                data = r.json()
                return data if isinstance(data, dict) else {}
            except Exception as e:
                last = e
                time.sleep(self.backoff_s * (2**i))

        raise last  # type: ignore[misc]

    def books(self, token_ids: List[str]) -> Dict[str, Any]:
        """
        Compatibility helper: fetch many books by calling book() per token_id.
        Returns: {token_id: book_dict} for non-empty results.
        """
        out: Dict[str, Any] = {}
        for tid in token_ids:
            if tid is None:
                continue
            try:
                b = self.book(str(tid))
                if isinstance(b, dict) and b:
                    out[str(tid)] = b
            except Exception:
                # swallow per-token errors so one bad token doesn't kill the batch
                continue
        return out