"""
Normalize raw Kalshi/Polymarket sports markets into NormalizedOutcome records.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from src.matching.models import NormalizedOutcome
from src.matching.team_aliases import canonicalize_team, league_from_kalshi_series, league_from_poly_sport

ET = ZoneInfo("America/New_York")

_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_kalshi_ticker_start(event_ticker: str) -> tuple[Optional[date], Optional[datetime]]:
    """
    Parse KXMLBGAME-26JUL121610TORSD → (date, start_time UTC).

    Kalshi sports tickers encode local US Eastern date + HHMM. Converting via ET
    keeps doubleheader ordering and aligns with Polymarket UTC start times.
    """
    m = re.search(r"-(\d{2})([A-Z]{3})(\d{2})(\d{4})", event_ticker or "")
    if not m:
        m_date = re.search(r"-(\d{2})([A-Z]{3})(\d{2})", event_ticker or "")
        if not m_date:
            return None, None
        yy, mon, dd = m_date.group(1), m_date.group(2), m_date.group(3)
        if mon not in _MONTHS:
            return None, None
        try:
            return date(2000 + int(yy), _MONTHS[mon], int(dd)), None
        except ValueError:
            return None, None

    yy, mon, dd, hhmm = m.group(1), m.group(2), m.group(3), m.group(4)
    if mon not in _MONTHS:
        return None, None
    try:
        d = date(2000 + int(yy), _MONTHS[mon], int(dd))
        hour, minute = int(hhmm[:2]), int(hhmm[2:])
        local = datetime(d.year, d.month, d.day, hour, minute, tzinfo=ET)
        return d, local.astimezone(timezone.utc)
    except ValueError:
        return None, None


def _parse_teams_from_title(title: str) -> tuple[str, str] | None:
    """
    Parse 'Team A vs Team B' / 'Team A vs. Team B' / 'Team A @ Team B'.
    """
    if not title:
        return None
    for sep in (r"\s+vs\.?\s+", r"\s+@\s+", r"\s+v\.?\s+"):
        parts = re.split(sep, title, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            left, right = parts[0].strip(), parts[1].strip()
            # Drop trailing market suffixes
            right = re.split(r"\s+[-–—]\s+", right, maxsplit=1)[0].strip()
            right = re.sub(r"\s+Winner\??$", "", right, flags=re.IGNORECASE).strip()
            if left and right:
                return left, right
    return None


def _is_moneyline_kalshi(market: dict[str, Any]) -> bool:
    title = str(market.get("title") or "")
    event_title = str(market.get("_event_title") or "")
    # Skip spreads/totals/props by keyword
    blob = f"{title} {event_title}".lower()
    for bad in ("spread", "total", "over", "under", "points", "strikeouts", "first 5", "prop", "parlay"):
        if bad in blob and "winner" not in blob:
            # still allow "Winner?" moneylines
            if "winner" in blob:
                continue
            return False
    yes = str(market.get("yes_sub_title") or "").strip()
    return bool(yes)


def normalize_kalshi_markets(raw_markets: list[dict[str, Any]]) -> list[NormalizedOutcome]:
    outcomes: list[NormalizedOutcome] = []
    for market in raw_markets:
        if not _is_moneyline_kalshi(market):
            continue
        series = str(market.get("_series_ticker") or "")
        league = league_from_kalshi_series(series)
        sport = league
        title = str(market.get("title") or market.get("_event_title") or "")
        yes_team_raw = str(market.get("yes_sub_title") or "").strip()
        parsed = _parse_teams_from_title(market.get("_event_title") or "") or _parse_teams_from_title(title)
        if not parsed:
            logging.debug("Skip Kalshi market without parseable teams: %s", market.get("ticker"))
            continue
        team_a_raw, team_b_raw = parsed
        team_a = canonicalize_team(league, team_a_raw)
        team_b = canonicalize_team(league, team_b_raw)
        outcome_team = canonicalize_team(league, yes_team_raw)
        if outcome_team not in {team_a, team_b}:
            if canonicalize_team(league, team_a_raw) == outcome_team:
                outcome_team = team_a
            elif canonicalize_team(league, team_b_raw) == outcome_team:
                outcome_team = team_b

        event_ticker = str(market.get("_event_ticker") or market.get("event_ticker") or "")
        ticker_date, ticker_start = _parse_kalshi_ticker_start(event_ticker)

        # Prefer API game-time fields; fall back to Eastern HHMM embedded in the ticker.
        start = (
            _parse_dt(market.get("occurrence_datetime"))
            or ticker_start
            or _parse_dt(market.get("expected_expiration_time"))
            or _parse_dt(market.get("close_time"))
        )
        start_date: Optional[date] = ticker_date or (start.date() if start else None)
        if start is not None and start_date is None:
            start_date = start.astimezone(timezone.utc).date()

        outcomes.append(
            NormalizedOutcome(
                exchange="kalshi",
                exchange_id=str(market.get("ticker") or ""),
                league=league,
                sport=sport,
                start_date=start_date,
                start_time=start,
                team_a=team_a,
                team_b=team_b,
                outcome_team=outcome_team,
                market_type="moneyline",
                title=title or str(market.get("_event_title") or ""),
                raw={
                    "yes_sub_title": yes_team_raw,
                    "event_ticker": event_ticker,
                    "series_ticker": series,
                },
            )
        )
    return outcomes


def normalize_poly_markets(raw_rows: list[dict[str, Any]]) -> list[NormalizedOutcome]:
    outcomes: list[NormalizedOutcome] = []
    for row in raw_rows:
        sport = str(row.get("sport") or "")
        league = league_from_poly_sport(sport)
        market_type = str(row.get("sports_market_type") or "").lower()
        if market_type and market_type not in {"moneyline", "ml"}:
            continue
        siblings = row.get("sibling_outcomes") or []
        if len(siblings) != 2:
            continue
        team_a = canonicalize_team(league, str(siblings[0]))
        team_b = canonicalize_team(league, str(siblings[1]))
        outcome_team = canonicalize_team(league, str(row.get("outcome_name") or ""))
        start = _parse_dt(row.get("start_time"))
        start_date = start.date() if start else None
        slug = str(row.get("slug") or "")
        if start_date is None:
            m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", slug)
            if m:
                try:
                    start_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except ValueError:
                    pass

        outcomes.append(
            NormalizedOutcome(
                exchange="polymarket",
                exchange_id=str(row.get("token_id") or ""),
                league=league,
                sport=sport or league,
                start_date=start_date,
                start_time=start,
                team_a=team_a,
                team_b=team_b,
                outcome_team=outcome_team,
                market_type="moneyline",
                title=str(row.get("question") or row.get("event_title") or ""),
                raw={
                    "slug": slug,
                    "sport": sport,
                    "outcome_name": row.get("outcome_name"),
                    "sibling_outcomes": siblings,
                },
            )
        )

    # One token per (game including start time, outcome) — keep doubleheaders distinct.
    deduped: dict[tuple, NormalizedOutcome] = {}
    for outcome in outcomes:
        key = (outcome.game_key, outcome.outcome_team)
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = outcome
            continue
        if "spread" in existing.title.lower() and "spread" not in outcome.title.lower():
            deduped[key] = outcome
    return list(deduped.values())
