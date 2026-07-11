"""
Shared data models for the sports market matcher.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal, Optional


MarketType = Literal["moneyline", "other"]
Confidence = Literal["high", "medium", "low"]
Exchange = Literal["kalshi", "polymarket"]


@dataclass(frozen=True)
class NormalizedOutcome:
    """
    One tradeable yes-side outcome on a single exchange, normalized for matching.
    """

    exchange: Exchange
    exchange_id: str  # Kalshi ticker or Polymarket CLOB token id
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
        """Stable key for the underlying game (unordered teams + league + date)."""
        teams = tuple(sorted((self.team_a, self.team_b)))
        return (self.league, self.start_date.isoformat() if self.start_date else "", teams)

    @property
    def opposite_team(self) -> str:
        if self.outcome_team == self.team_a:
            return self.team_b
        return self.team_a


@dataclass
class MatchCandidate:
    """
    A proposed opposite-side arb pair: Polymarket token vs Kalshi ticker.
    """

    poly: NormalizedOutcome
    kalshi: NormalizedOutcome
    score: float
    reason: str
    needs_ai: bool = False


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
