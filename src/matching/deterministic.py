"""
Deterministic matching of Kalshi and Polymarket moneyline outcomes.

Builds opposite-side arb pairs (Poly team A ↔ Kalshi team B) when the underlying
game matches with high confidence. Ambiguous leftovers are flagged for AI/review.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from src.matching.models import MatchCandidate, MatchDecision, MatchResult, NormalizedOutcome


HIGH_SCORE = 0.9
AMBIGUOUS_SCORE = 0.55


def _teams_set(o: NormalizedOutcome) -> frozenset[str]:
    return frozenset({o.team_a, o.team_b})


def _same_game(a: NormalizedOutcome, b: NormalizedOutcome) -> tuple[float, str, bool]:
    """
    Return (score, reason, needs_ai).
    """
    if a.market_type != "moneyline" or b.market_type != "moneyline":
        return 0.0, "non_moneyline", False

    league_match = a.league and a.league == b.league
    teams_a = _teams_set(a)
    teams_b = _teams_set(b)
    teams_match = len(teams_a) == 2 and teams_a == teams_b
    date_match = bool(a.start_date and b.start_date and a.start_date == b.start_date)
    date_missing = a.start_date is None or b.start_date is None

    # Outcome must be a known side of the game
    if a.outcome_team not in teams_a or b.outcome_team not in teams_b:
        return 0.2, "outcome_not_in_team_set", True

    if league_match and teams_match and date_match:
        return 1.0, "league+teams+date", False
    if league_match and teams_match and date_missing:
        return 0.7, "league+teams_date_missing", True
    if teams_match and date_match and not league_match:
        return 0.65, "teams+date_league_mismatch", True
    if league_match and teams_match and not date_match:
        # Same teams/league different date — likely different games
        return 0.35, "league+teams_date_mismatch", True
    if league_match and len(teams_a & teams_b) == 1 and date_match:
        return 0.45, "partial_team_overlap", True
    return 0.0, "no_match", False


def build_candidates(
    kalshi_outcomes: Iterable[NormalizedOutcome],
    poly_outcomes: Iterable[NormalizedOutcome],
) -> tuple[list[MatchCandidate], list[MatchCandidate]]:
    """
    Build high-confidence and ambiguous opposite-side candidates.
    """
    high: list[MatchCandidate] = []
    ambiguous: list[MatchCandidate] = []
    seen: set[tuple[str, str]] = set()

    kalshi_list = list(kalshi_outcomes)
    poly_list = list(poly_outcomes)

    # Index poly by league for speed
    poly_by_league: dict[str, list[NormalizedOutcome]] = defaultdict(list)
    for p in poly_list:
        poly_by_league[p.league].append(p)

    for k in kalshi_list:
        pool = list(poly_by_league.get(k.league) or [])
        # If league unknown/empty, search all (expensive but rare)
        if not pool and not k.league:
            pool = poly_list
        for p in pool:
            score, reason, needs_ai = _same_game(k, p)
            if score < AMBIGUOUS_SCORE:
                continue
            # Opposite-side arb pair only
            if p.outcome_team == k.outcome_team:
                continue
            if p.outcome_team != k.opposite_team and k.outcome_team != p.opposite_team:
                # Still allow if both are on the game but not exact opposite mapping
                if p.outcome_team not in _teams_set(k):
                    continue
                needs_ai = True
                reason = reason + "+outcome_side_unclear"

            pair_key = (p.exchange_id, k.exchange_id)
            if pair_key in seen:
                continue
            seen.add(pair_key)

            candidate = MatchCandidate(
                poly=p,
                kalshi=k,
                score=score,
                reason=reason,
                needs_ai=needs_ai or score < HIGH_SCORE,
            )
            if score >= HIGH_SCORE and not candidate.needs_ai:
                high.append(candidate)
            else:
                ambiguous.append(candidate)

    return high, ambiguous


def decisions_from_high_confidence(candidates: list[MatchCandidate]) -> list[MatchDecision]:
    return [
        MatchDecision(
            candidate=c,
            accepted=True,
            confidence="high",
            source="deterministic",
            detail=c.reason,
        )
        for c in candidates
    ]


def review_decisions(candidates: list[MatchCandidate], detail_prefix: str = "") -> list[MatchDecision]:
    return [
        MatchDecision(
            candidate=c,
            accepted=False,
            confidence="medium" if c.score >= AMBIGUOUS_SCORE else "low",
            source="rejected",
            detail=f"{detail_prefix}{c.reason}".strip(),
        )
        for c in candidates
    ]


def merge_results(*parts: MatchResult) -> MatchResult:
    out = MatchResult()
    for part in parts:
        out.accepted.extend(part.accepted)
        out.review.extend(part.review)
        out.skipped.extend(part.skipped)
    return out
