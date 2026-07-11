"""
Optional Kalshi market-status helper for opportunity logging.

Kept separate from the gap tracker so status fetching can be swapped, mocked,
or skipped without touching the CSV / lifecycle logic.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from src.kalshi_modules.generate_kalshi_credentials import get_kalshi_headers


class KalshiMarketStatusCache:
    """
    Cache Kalshi market status strings (active, closed, settled, etc.) with a TTL.
    """

    def __init__(self, ttl_seconds: float = 60.0, timeout_seconds: float = 5.0):
        self.ttl_seconds = ttl_seconds
        self.timeout_seconds = timeout_seconds
        self._cache: dict[str, tuple[float, str]] = {}

    def get(self, ticker: str) -> str:
        """
        Return a status string for the ticker, or "unknown" on failure.
        """
        now = time.monotonic()
        cached = self._cache.get(ticker)
        if cached is not None and now - cached[0] < self.ttl_seconds:
            return cached[1]

        status = self._fetch(ticker) or "unknown"
        self._cache[ticker] = (now, status)
        return status

    def _fetch(self, ticker: str) -> Optional[str]:
        url = f"https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}"
        try:
            headers = get_kalshi_headers(url, method="GET")
            response = requests.get(url, headers=headers, timeout=self.timeout_seconds)
            if response.status_code >= 400:
                logging.warning(
                    "Kalshi market status fetch failed for %s: %s %s",
                    ticker,
                    response.status_code,
                    response.text[:200],
                )
                return None
            market = response.json().get("market") or response.json()
            return str(market.get("status") or "unknown")
        except Exception:
            logging.exception("Kalshi market status fetch error for %s", ticker)
            return None
