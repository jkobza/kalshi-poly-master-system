"""
Discover open Polymarket US sports moneyline / game-winner markets.

Uses the public gateway (no auth): https://gateway.polymarket.us
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import requests

US_GATEWAY = "https://gateway.polymarket.us"
DEFAULT_HEADERS = {
    "User-Agent": "kalshi-poly-arb-matcher/1.0",
    "Accept": "application/json",
}

# US sportsMarketType values that behave like binary game moneylines.
_WINNER_TYPES = {
    "moneyline",
    "ml",
    "baseball_team_full_game_winner",
    "basketball_team_full_game_winner",
    "football_team_full_game_winner",
    "tennis_match_winner",
    "table_tennis_match_winner",
    "ufc_fight_winner",
    "esports_match_winner",
    "cricket_match_winner",
}


def _get_json(path: str, params: Optional[dict] = None, timeout: float = 45.0) -> Any:
    url = f"{US_GATEWAY}{path}"
    response = requests.get(url, params=params or {}, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _is_winner_moneyline(market: dict[str, Any]) -> bool:
    market_type = str(market.get("sportsMarketType") or market.get("marketType") or "").lower()
    if market_type == "futures" or market_type.endswith("_futures"):
        return False
    if market_type in _WINNER_TYPES:
        return True
    # Newer US enums often end in _winner (game / match winner).
    return market_type.endswith("_winner") and "prop" not in market_type


def _league_from_market(market: dict[str, Any], sides: list[dict[str, Any]]) -> str:
    for side in sides:
        team = side.get("team") or {}
        league = str(team.get("league") or "").strip().lower()
        if league:
            return league
    slug = str(market.get("slug") or "")
    parts = slug.split("-")
    # aec-mlb-wsh-phi-2026-08-04 → mlb
    if len(parts) >= 2:
        return parts[1].lower()
    return ""


def fetch_open_moneyline_markets(
    page_size: int = 100,
    max_pages: int = 50,
) -> list[dict[str, Any]]:
    """
    Paginate active, non-closed markets with marketTypes=moneyline.

    Polymarket US uses this filter for game/match winners (not only classic
    sportsMarketType=moneyline). Futures are filtered out client-side.
    """
    markets: list[dict[str, Any]] = []
    offset = 0
    for _ in range(max_pages):
        data = _get_json(
            "/v1/markets",
            params={
                "limit": page_size,
                "offset": offset,
                "closed": "false",
                "active": "true",
                "marketTypes": "moneyline",
            },
        )
        batch = data.get("markets") if isinstance(data, dict) else data
        if not isinstance(batch, list) or not batch:
            break
        for market in batch:
            if market.get("closed"):
                continue
            if not market.get("active", True):
                continue
            if not _is_winner_moneyline(market):
                continue
            markets.append(market)
        if len(batch) < page_size:
            break
        offset += len(batch)
    return markets


def discover_poly_us_moneyline_markets(
    sport_filter: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Return annotated Polymarket US moneyline outcome rows.

    Each item includes:
      exchange_id (slug:abbr), outcome_name, question, event_title, start_time,
      sport, slug, side_id, sibling_outcomes, raw_market
    """
    try:
        markets = fetch_open_moneyline_markets()
    except Exception:
        logging.exception("Polymarket US market fetch failed")
        return []

    needle = (sport_filter or "").lower().strip()
    rows: list[dict[str, Any]] = []

    for market in markets:
        sides = market.get("marketSides") or []
        if not isinstance(sides, list) or len(sides) != 2:
            continue

        league = _league_from_market(market, sides)
        slug = str(market.get("slug") or "")
        if needle and needle not in league and needle not in slug.lower():
            # Also allow aliases like ncaab/cbb via broader contains
            continue

        start_time = (
            market.get("gameStartTime")
            or market.get("startTime")
            or market.get("startDate")
            or market.get("endDate")
        )
        question = str(market.get("question") or "")
        sibling_names: list[str] = []
        side_meta: list[tuple[str, str, dict]] = []
        for side in sides:
            team = side.get("team") or {}
            name = (
                str(team.get("name") or "").strip()
                or str(side.get("description") or "").strip()
                or str(team.get("displayAbbreviation") or "").strip()
            )
            abbr = str(team.get("abbreviation") or "").strip().lower()
            if not name:
                continue
            sibling_names.append(name)
            side_meta.append((name, abbr, side))

        if len(side_meta) != 2:
            continue

        for name, abbr, side in side_meta:
            # Slug alone is shared by both sides; qualify with abbr (or side id).
            qual = abbr or str(side.get("id") or name)
            exchange_id = f"{slug}:{qual}"
            rows.append(
                {
                    "token_id": exchange_id,
                    "exchange_id": exchange_id,
                    "outcome_name": name,
                    "outcome_abbr": abbr,
                    "side_id": str(side.get("id") or ""),
                    "question": question,
                    "event_title": question,
                    "slug": slug,
                    "start_time": start_time,
                    "sport": league,
                    "series_id": "",
                    "sibling_outcomes": sibling_names,
                    "sibling_token_ids": [
                        f"{slug}:{(side_meta[0][1] or side_meta[0][0])}",
                        f"{slug}:{(side_meta[1][1] or side_meta[1][0])}",
                    ],
                    "sports_market_type": str(
                        market.get("sportsMarketType") or market.get("marketType") or "moneyline"
                    ),
                    "raw_market": market,
                    "raw_event": {
                        "id": market.get("id"),
                        "title": question,
                        "slug": slug,
                        "startTime": start_time,
                    },
                }
            )

    logging.info("Polymarket US discovery: %s moneyline outcome rows", len(rows))
    return rows
