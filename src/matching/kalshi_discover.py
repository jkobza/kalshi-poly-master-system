"""
Discover open Kalshi sports game markets via the events API.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Iterable, Optional

import requests

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
DEFAULT_SERIES = [
    "KXMLBGAME",
    "KXNBAGAME",
    "KXNHLGAME",
    "KXNFLGAME",
    "KXWNBAGAME",
    "KXNCAAFGAME",
    "KXNCAAMBGAME",
    "KXNCAAWBGAME",
    "KXEPLGAME",
    "KXMLSGAME",
    "KXLALIGAGAME",
]


def _get_json(
    path: str,
    params: Optional[dict] = None,
    timeout: float = 30.0,
    max_retries: int = 5,
) -> dict[str, Any]:
    url = f"{KALSHI_BASE}{path}"
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params or {}, timeout=timeout)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and str(retry_after).isdigit() else min(2 ** attempt, 20)
                logging.warning("Kalshi rate limited on %s; sleeping %.1fs", path, wait)
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            wait = min(2 ** attempt, 20)
            logging.warning("Kalshi request failed (%s); retry in %.1fs", exc, wait)
            time.sleep(wait)
    assert last_error is not None
    raise last_error


def list_game_series_tickers(extra: Optional[Iterable[str]] = None) -> list[str]:
    """
    Return sports series tickers that look like single-game moneyline series (*GAME).

    Excludes all-star / futures-style *ASGAME / *FTGAME / *GAMES variants when possible.
    Falls back to a known list when the series catalog call fails.
    """
    tickers: set[str] = set(DEFAULT_SERIES)
    if extra:
        tickers.update(str(t).upper() for t in extra)
    try:
        data = _get_json("/series", params={"category": "Sports"})
        for series in data.get("series") or []:
            ticker = str(series.get("ticker") or "").upper()
            if not ticker.endswith("GAME"):
                continue
            if any(bad in ticker for bad in ("GAMES", "SERIES", "ASGAME", "FTGAME", "CELEBRITY", "ALLSTAR")):
                continue
            tickers.add(ticker)
    except Exception:
        logging.exception("Failed to list Kalshi sports series; using defaults")
    return sorted(tickers)


def fetch_open_events_for_series(series_ticker: str, limit: int = 200) -> list[dict[str, Any]]:
    """
    Paginate open events (with nested markets) for one Kalshi series.
    """
    events: list[dict[str, Any]] = []
    cursor: Optional[str] = None
    while True:
        params: dict[str, Any] = {
            "series_ticker": series_ticker,
            "status": "open",
            "with_nested_markets": "true",
            "limit": min(limit, 200),
        }
        if cursor:
            params["cursor"] = cursor
        data = _get_json("/events", params=params)
        batch = data.get("events") or []
        events.extend(batch)
        cursor = data.get("cursor") or None
        if not cursor or not batch:
            break
        if len(events) >= limit * 5:
            break
        time.sleep(0.15)
    return events


def discover_kalshi_game_markets(
    series_filter: Optional[Iterable[str]] = None,
    sport_filter: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Return raw Kalshi market dicts annotated with series/event metadata.

    Each item is the nested market object plus:
      _series_ticker, _event_ticker, _event_title, _event_subtitle
    """
    series_list = list_game_series_tickers(series_filter)
    if sport_filter:
        needle = sport_filter.upper()
        preferred = f"KX{needle}GAME"
        exact = [s for s in series_list if s == preferred]
        if exact:
            series_list = exact
        else:
            series_list = [
                s for s in series_list
                if needle in s and s.endswith("GAME")
                and "ASGAME" not in s and "FTGAME" not in s
            ]

    markets: list[dict[str, Any]] = []
    for series_ticker in series_list:
        try:
            events = fetch_open_events_for_series(series_ticker)
        except Exception:
            logging.exception("Kalshi event fetch failed for %s", series_ticker)
            continue
        for event in events:
            for market in event.get("markets") or []:
                status = str(market.get("status") or "").lower()
                if status not in {"open", "active", ""}:
                    # Keep active/open; skip finalized
                    if status in {"determined", "finalized", "settled", "closed"}:
                        continue
                annotated = dict(market)
                annotated["_series_ticker"] = series_ticker
                annotated["_event_ticker"] = event.get("event_ticker")
                annotated["_event_title"] = event.get("title") or ""
                annotated["_event_subtitle"] = event.get("sub_title") or ""
                markets.append(annotated)
        time.sleep(0.2)
    logging.info("Kalshi discovery: %s markets across %s series", len(markets), len(series_list))
    return markets
