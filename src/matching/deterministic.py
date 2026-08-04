"""
Deterministic matching of sports moneyline outcomes across venues.

Builds opposite-side arb pairs between any two venues (kalshi, poly_global,
poly_us) when the underlying game matches with high confidence. Ambiguous
leftovers are flagged for AI/review.

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

VENUE_ORDER = {"kalshi": 0, "poly_global": 1, "poly_us": 2, "polymarket": 1}


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


def _order_legs(a: NormalizedOutcome, b: NormalizedOutcome) -> tuple[NormalizedOutcome, NormalizedOutcome]:
    oa = VENUE_ORDER.get(a.exchange, 9)
    ob = VENUE_ORDER.get(b.exchange, 9)
    if oa < ob or (oa == ob and a.exchange_id <= b.exchange_id):
        return a, b
    return b, a


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
    *outcome_groups: Iterable[NormalizedOutcome],
) -> tuple[list[MatchCandidate], list[MatchCandidate]]:
    """
    Build high-confidence and ambiguous opposite-side candidates across venues.

    Accepts one or more outcome iterables (kalshi, poly_global, poly_us, ...).
    For each ordered venue pair, keep the closest start-time opposite-side match
    per (leg, counterparty_venue).
    """
    high: list[MatchCandidate] = []
    ambiguous: list[MatchCandidate] = []
    seen: set[tuple[str, str, str, str]] = set()

    outcomes = [o for group in outcome_groups for o in group]
    by_venue: dict[str, list[NormalizedOutcome]] = defaultdict(list)
    by_league: dict[str, list[NormalizedOutcome]] = defaultdict(list)
    for o in outcomes:
        by_venue[o.exchange].append(o)
        by_league[o.league].append(o)

    venues = sorted(by_venue.keys(), key=lambda v: VENUE_ORDER.get(v, 9))
    provisional: list[MatchCandidate] = []

    for i, venue_a in enumerate(venues):
        for venue_b in venues[i + 1 :]:
            for a in by_venue[venue_a]:
                pool = [b for b in by_league.get(a.league, []) if b.exchange == venue_b]
                if not pool and not a.league:
                    pool = list(by_venue[venue_b])
                for b in pool:
                    score, reason, needs_ai = _same_game(a, b)
                    if score < AMBIGUOUS_SCORE:
                        continue
                    if b.outcome_team == a.outcome_team:
                        continue
                    if b.outcome_team != a.opposite_team and a.outcome_team != b.opposite_team:
                        if b.outcome_team not in _teams_set(a):
                            continue
                        needs_ai = True
                        reason = reason + "+outcome_side_unclear"

                    leg_a, leg_b = _order_legs(a, b)
                    pair_key = (leg_a.exchange, leg_a.exchange_id, leg_b.exchange, leg_b.exchange_id)
                    if pair_key in seen:
                        continue
                    seen.add(pair_key)

                    provisional.append(
                        MatchCandidate(
                            leg_a=leg_a,
                            leg_b=leg_b,
                            score=score,
                            reason=reason,
                            needs_ai=needs_ai or score < HIGH_SCORE,
                        )
                    )

    # Keep closest start-time high-confidence match per (leg, counterparty venue).
    best: dict[tuple[str, str, str], MatchCandidate] = {}
    for c in provisional:
        if c.score < HIGH_SCORE or c.needs_ai:
            ambiguous.append(c)
            continue

        keys = [
            (c.leg_a.exchange, c.leg_a.exchange_id, c.leg_b.exchange),
            (c.leg_b.exchange, c.leg_b.exchange_id, c.leg_a.exchange),
        ]
        # One candidate occupies both directed keys; demote if either is superseded.
        replace_existing: list[MatchCandidate] = []
        keep = True
        for key in keys:
            existing = best.get(key)
            if existing is None:
                continue
            if existing is c:
                continue
            d_new = _time_delta_minutes(c.leg_a.start_time, c.leg_b.start_time)
            d_old = _time_delta_minutes(existing.leg_a.start_time, existing.leg_b.start_time)
            better = False
            if d_new is not None and d_old is not None and d_new < d_old:
                better = True
            elif (d_new is None) == (d_old is None) and c.score > existing.score:
                better = True
            elif d_old is None and d_new is not None:
                better = True
            if better:
                replace_existing.append(existing)
            else:
                keep = False
                break

        if not keep:
            c.needs_ai = True
            c.reason = c.reason + "+superseded_by_closer_start_time"
            ambiguous.append(c)
            continue

        for existing in replace_existing:
            if existing.needs_ai and "+superseded_by_closer_start_time" in existing.reason:
                continue
            existing.needs_ai = True
            existing.reason = existing.reason + "+superseded_by_closer_start_time"
            ambiguous.append(existing)
            # Drop superseded from best map
            for key, val in list(best.items()):
                if val is existing:
                    del best[key]

        for key in keys:
            best[key] = c

    # Unique candidates (each stored under two keys)
    unique_high: list[MatchCandidate] = []
    seen_ids: set[int] = set()
    for c in best.values():
        cid = id(c)
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        unique_high.append(c)

    high.extend(unique_high)
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
