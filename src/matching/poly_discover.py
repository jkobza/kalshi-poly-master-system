"""
Discover open Polymarket sports moneyline markets via the Gamma API.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Optional

import requests

GAMMA_BASE = "https://gamma-api.polymarket.com"
DEFAULT_HEADERS = {"User-Agent": "kalshi-poly-arb-matcher/1.0"}


def _get_json(path: str, params: Optional[dict] = None, timeout: float = 30.0) -> Any:
    url = f"{GAMMA_BASE}{path}"
    response = requests.get(url, params=params or {}, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.json()


def list_sports() -> list[dict[str, Any]]:
    data = _get_json("/sports")
    return data if isinstance(data, list) else []


def _parse_maybe_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def fetch_events_for_series(series_id: str, page_size: int = 50, max_pages: int = 20) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    offset = 0
    for _ in range(max_pages):
        batch = _get_json(
            "/events",
            params={
                "series_id": series_id,
                "active": "true",
                "closed": "false",
                "limit": page_size,
                "offset": offset,
            },
        )
        if not isinstance(batch, list) or not batch:
            break
        events.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return events


def discover_poly_moneyline_markets(
    sport_filter: Optional[str] = None,
    sports: Optional[Iterable[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    """
    Return annotated Polymarket moneyline outcome rows.

    Each item includes:
      token_id, outcome_name, question, event_title, start_time, sport, series_id,
      sibling_outcomes, sibling_token_ids, raw_market, raw_event
    """
    sports_list = list(sports) if sports is not None else list_sports()
    if sport_filter:
        needle = sport_filter.lower()
        sports_list = [
            s for s in sports_list
            if needle in str(s.get("sport") or "").lower()
            or needle in str(s.get("series") or "").lower()
        ]

    rows: list[dict[str, Any]] = []
    for sport in sports_list:
        sport_slug = str(sport.get("sport") or "")
        series_id = str(sport.get("series") or "").strip()
        if not series_id:
            continue
        try:
            events = fetch_events_for_series(series_id)
        except Exception:
            logging.exception("Polymarket event fetch failed for sport=%s series=%s", sport_slug, series_id)
            continue

        for event in events:
            if event.get("closed"):
                continue
            start_time = event.get("startTime") or event.get("startDate") or event.get("eventDate")
            for market in event.get("markets") or []:
                if market.get("closed"):
                    continue
                if not market.get("active", True):
                    continue
                market_type = str(market.get("sportsMarketType") or "").lower()
                # Accept explicit moneyline; also accept missing type when question looks like a game winner
                if market_type and market_type not in {"moneyline", "ml"}:
                    continue

                outcomes = _parse_maybe_json(market.get("outcomes")) or []
                token_ids = _parse_maybe_json(market.get("clobTokenIds")) or []
                if not isinstance(outcomes, list) or not isinstance(token_ids, list):
                    continue
                if len(outcomes) != 2 or len(token_ids) != 2:
                    # Moneyline should be binary team vs team
                    continue

                for outcome_name, token_id in zip(outcomes, token_ids):
                    rows.append(
                        {
                            "token_id": str(token_id),
                            "outcome_name": str(outcome_name),
                            "question": market.get("question") or event.get("title") or "",
                            "event_title": event.get("title") or "",
                            "slug": market.get("slug") or event.get("slug") or "",
                            "start_time": start_time,
                            "sport": sport_slug,
                            "series_id": series_id,
                            "sibling_outcomes": [str(o) for o in outcomes],
                            "sibling_token_ids": [str(t) for t in token_ids],
                            "sports_market_type": market_type or "moneyline",
                            "raw_market": market,
                            "raw_event": {
                                "id": event.get("id"),
                                "title": event.get("title"),
                                "slug": event.get("slug"),
                                "startTime": start_time,
                            },
                        }
                    )

    logging.info("Polymarket discovery: %s moneyline outcome rows", len(rows))
    return rows
