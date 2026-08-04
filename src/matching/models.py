"""
Shared data models for the sports market matcher.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal, Optional


MarketType = Literal["moneyline", "other"]
Confidence = Literal["high", "medium", "low"]
# Venue tags written to matchedtable.csv exchange_a / exchange_b.
Exchange = Literal["kalshi", "poly_global", "poly_us"]


@dataclass(frozen=True)
class NormalizedOutcome:
    """
    One tradeable yes-side outcome on a single exchange, normalized for matching.
    """

    exchange: Exchange
    exchange_id: str  # Kalshi ticker, Global CLOB token id, or US market slug
    league: str
    sport: str
    start_date: Optional[date]
    start_time: Optional[datetime]
    team_a: str  # canonical code or normalized name
    team_b: str
    outcome_team: str  # which team this contract pays on
    market_type: MarketType
    title: str
    raw: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    @property
    def game_key(self) -> tuple:
        """
        Stable key for the underlying game (unordered teams + league + date + start).

        Start time is bucketed to the minute so doubleheaders the same day stay distinct.
        """
        teams = tuple(sorted((self.team_a, self.team_b)))
        day = self.start_date.isoformat() if self.start_date else ""
        if self.start_time is not None:
            ts = self.start_time if self.start_time.tzinfo else self.start_time.replace(tzinfo=None)
            time_key = ts.strftime("%Y-%m-%dT%H:%M")
        else:
            time_key = ""
        return (self.league, day, teams, time_key)

    @property
    def opposite_team(self) -> str:
        if self.outcome_team == self.team_a:
            return self.team_b
        return self.team_a


@dataclass
class MatchCandidate:
    """
    A proposed opposite-side arb pair between any two venues.
    """

    leg_a: NormalizedOutcome
    leg_b: NormalizedOutcome
    score: float
    reason: str
    needs_ai: bool = False

    # Back-compat aliases used by older call sites / AI payload helpers.
    @property
    def kalshi(self) -> NormalizedOutcome:
        if self.leg_a.exchange == "kalshi":
            return self.leg_a
        if self.leg_b.exchange == "kalshi":
            return self.leg_b
        return self.leg_a

    @property
    def poly(self) -> NormalizedOutcome:
        if self.leg_a.exchange.startswith("poly"):
            return self.leg_a
        if self.leg_b.exchange.startswith("poly"):
            return self.leg_b
        return self.leg_b


@dataclass
class MatchDecision:
    """
    Final accept/review decision for one candidate.
    """

    candidate: MatchCandidate
    accepted: bool
    confidence: Confidence
    source: str  # "deterministic" | "ai" | "rejected"
    detail: str = ""


@dataclass
class MatchResult:
    accepted: list[MatchDecision] = field(default_factory=list)
    review: list[MatchDecision] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        return {
            "accepted": len(self.accepted),
            "review": len(self.review),
            "skipped": len(self.skipped),
        }
