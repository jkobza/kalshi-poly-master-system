"""
Deterministic matching of Kalshi and Polymarket moneyline outcomes.

Builds opposite-side arb pairs (Poly team A ↔ Kalshi team B) when the underlying
game matches with high confidence. Ambiguous leftovers are flagged for AI/review.

High-confidence auto-accept requires league + teams + date + start times within
START_TIME_TOLERANCE_MINUTES so doubleheaders on the same day do not cross-match.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable, Optional

from src.matching.models import MatchCandidate, MatchDecision, MatchResult, NormalizedOutcome


HIGH_SCORE = 0.9
AMBIGUOUS_SCORE = 0.55
# Same game if both start times fall within this window (handles minor feed skew).
START_TIME_TOLERANCE_MINUTES = 45


def _teams_set(o: NormalizedOutcome) -> frozenset[str]:
    return frozenset({o.team_a, o.team_b})


def _time_delta_minutes(a: Optional[datetime], b: Optional[datetime]) -> Optional[float]:
    if a is None or b is None:
        return None
    if a.tzinfo is None:
        a = a.replace(tzinfo=timezone.utc)
    if b.tzinfo is None:
        b = b.replace(tzinfo=timezone.utc)
    return abs((a - b).total_seconds()) / 60.0


def _same_game(a: NormalizedOutcome, b: NormalizedOutcome) -> tuple[float, str, bool]:
    """
    Return (score, reason, needs_ai).

    Auto-accept (needs_ai=False, score>=0.9) only when league, teams, date, and
    start times agree. Same teams on the same date with mismatched or missing
    times is treated as ambiguous so doubleheaders are not blindly paired.
    """
    if a.market_type != "moneyline" or b.market_type != "moneyline":
        return 0.0, "non_moneyline", False

    league_match = a.league and a.league == b.league
    teams_a = _teams_set(a)
    teams_b = _teams_set(b)
    teams_match = len(teams_a) == 2 and teams_a == teams_b
    date_match = bool(a.start_date and b.start_date and a.start_date == b.start_date)
    date_missing = a.start_date is None or b.start_date is None
    delta_min = _time_delta_minutes(a.start_time, b.start_time)
    times_present = delta_min is not None
    times_close = times_present and delta_min <= START_TIME_TOLERANCE_MINUTES
    times_far = times_present and delta_min > START_TIME_TOLERANCE_MINUTES

    # Outcome must be a known side of the game
    if a.outcome_team not in teams_a or b.outcome_team not in teams_b:
        return 0.2, "outcome_not_in_team_set", True

    # Strongest: league + teams + date + start times within tolerance
    if league_match and teams_match and date_match and times_close:
        return 1.0, f"league+teams+date+time(delta_min={delta_min:.1f})", False

    # Same day/teams but start times clearly different → different games (e.g. doubleheader)
    if league_match and teams_match and date_match and times_far:
        return 0.25, f"league+teams+date_time_mismatch(delta_min={delta_min:.1f})", False

    # Same day/teams but missing time on one/both sides → do not auto-accept
    if league_match and teams_match and date_match and not times_present:
        return 0.75, "league+teams+date_time_missing", True

    if league_match and teams_match and date_missing and times_close:
        return 0.85, f"league+teams+time_date_missing(delta_min={delta_min:.1f})", True

    if league_match and teams_match and date_missing:
        return 0.7, "league+teams_date_missing", True

    if teams_match and date_match and times_close and not league_match:
        return 0.65, "teams+date+time_league_mismatch", True

    if teams_match and date_match and not league_match:
        return 0.6, "teams+date_league_mismatch", True

    if league_match and teams_match and not date_match and not date_missing:
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

    When multiple Poly outcomes could match one Kalshi market, keep the closest
    start-time pairing for high-confidence accepts.
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

    # Collect scored opposite-side candidates, then pick best time match per kalshi/poly side.
    provisional: list[MatchCandidate] = []

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

            provisional.append(
                MatchCandidate(
                    poly=p,
                    kalshi=k,
                    score=score,
                    reason=reason,
                    needs_ai=needs_ai or score < HIGH_SCORE,
                )
            )

    # For each Kalshi id, if several high-confidence Poly opposite sides exist,
    # keep only the closest start-time match (or highest score).
    best_by_kalshi: dict[str, MatchCandidate] = {}
    for c in provisional:
        if c.score < HIGH_SCORE or c.needs_ai:
            ambiguous.append(c)
            continue
        kid = c.kalshi.exchange_id
        existing = best_by_kalshi.get(kid)
        if existing is None:
            best_by_kalshi[kid] = c
            continue
        # Prefer closer start times, then higher score
        d_new = _time_delta_minutes(c.kalshi.start_time, c.poly.start_time)
        d_old = _time_delta_minutes(existing.kalshi.start_time, existing.poly.start_time)
        replace = False
        if d_new is not None and d_old is not None and d_new < d_old:
            replace = True
        elif (d_new is None) == (d_old is None) and c.score > existing.score:
            replace = True
        elif d_old is None and d_new is not None:
            replace = True
        if replace:
            # Demote the worse same-day candidate to review rather than silently drop
            existing.needs_ai = True
            existing.reason = existing.reason + "+superseded_by_closer_start_time"
            ambiguous.append(existing)
            best_by_kalshi[kid] = c
        else:
            c.needs_ai = True
            c.reason = c.reason + "+superseded_by_closer_start_time"
            ambiguous.append(c)

    high.extend(best_by_kalshi.values())
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
