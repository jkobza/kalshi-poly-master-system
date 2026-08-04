"""
CLI entrypoint for sports market matching across Kalshi, Polymarket Global, and Polymarket US.

Examples:
  python -m src.matching.run_matcher
  python -m src.matching.run_matcher --write
  python -m src.matching.run_matcher --sport mlb --write
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.matching.ai_verifier import verify_ambiguous
from src.matching.deterministic import build_candidates, decisions_from_high_confidence
from src.matching.kalshi_discover import discover_kalshi_game_markets
from src.matching.models import MatchDecision, MatchResult
from src.matching.normalize import (
    normalize_kalshi_markets,
    normalize_poly_markets,
    normalize_poly_us_markets,
)
from src.matching.poly_discover import discover_poly_moneyline_markets
from src.matching.poly_us_discover import discover_poly_us_moneyline_markets
from src.matching.writer import DEFAULT_MATCHED_PATH, DEFAULT_REVIEW_PATH, write_match_outputs

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = PROJECT_ROOT / "logs" / "matcher.log"


def setup_logging(verbose: bool = False) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    file_handler = logging.FileHandler(LOG_PATH)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    root.addHandler(console)
    root.addHandler(file_handler)


def run_match(sport: str | None = None, use_ai: bool = True) -> MatchResult:
    logging.info("Discovering Kalshi markets%s...", f" (filter={sport})" if sport else "")
    kalshi_raw = discover_kalshi_game_markets(sport_filter=sport)
    logging.info("Discovering Polymarket Global markets%s...", f" (filter={sport})" if sport else "")
    poly_global_raw = discover_poly_moneyline_markets(sport_filter=sport)
    logging.info("Discovering Polymarket US markets%s...", f" (filter={sport})" if sport else "")
    poly_us_raw = discover_poly_us_moneyline_markets(sport_filter=sport)

    kalshi_norm = normalize_kalshi_markets(kalshi_raw)
    poly_global_norm = normalize_poly_markets(poly_global_raw)
    poly_us_norm = normalize_poly_us_markets(poly_us_raw)
    logging.info(
        "Normalized outcomes: kalshi=%s poly_global=%s poly_us=%s",
        len(kalshi_norm),
        len(poly_global_norm),
        len(poly_us_norm),
    )

    high, ambiguous = build_candidates(kalshi_norm, poly_global_norm, poly_us_norm)
    logging.info("Deterministic candidates: high=%s ambiguous=%s", len(high), len(ambiguous))

    result = MatchResult()
    result.accepted.extend(decisions_from_high_confidence(high))

    if ambiguous:
        if use_ai:
            logging.info("Running AI verifier on %s ambiguous candidates...", len(ambiguous))
            ai_decisions = verify_ambiguous(ambiguous)
            for decision in ai_decisions:
                if decision.accepted:
                    result.accepted.append(decision)
                else:
                    result.review.append(decision)
        else:
            logging.info("AI disabled; sending %s ambiguous candidates to review", len(ambiguous))
            for c in ambiguous:
                result.review.append(
                    MatchDecision(
                        candidate=c,
                        accepted=False,
                        confidence="medium",
                        source="rejected",
                        detail="ai_disabled:" + c.reason,
                    )
                )

    # Deduplicate identical pairs. Allow the same ticker to appear in multiple
    # rows when the counterparty venue differs (e.g. Kalshi↔Global and Kalshi↔US).
    seen_pairs: set[tuple[tuple[str, str], tuple[str, str]]] = set()
    used_with_venue: set[tuple[str, str, str]] = set()
    unique_accepted: list[MatchDecision] = []
    for decision in result.accepted:
        a = decision.candidate.leg_a
        b = decision.candidate.leg_b
        leg_a = (a.exchange, a.exchange_id)
        leg_b = (b.exchange, b.exchange_id)
        key = tuple(sorted((leg_a, leg_b)))
        if key in seen_pairs:
            continue
        lock_a = (a.exchange, a.exchange_id, b.exchange)
        lock_b = (b.exchange, b.exchange_id, a.exchange)
        if lock_a in used_with_venue or lock_b in used_with_venue:
            result.review.append(
                MatchDecision(
                    candidate=decision.candidate,
                    accepted=False,
                    confidence="medium",
                    source="rejected",
                    detail="duplicate_side_id:" + decision.detail,
                )
            )
            continue
        seen_pairs.add(key)
        used_with_venue.add(lock_a)
        used_with_venue.add(lock_b)
        unique_accepted.append(decision)
    result.accepted = unique_accepted
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Match Kalshi / Polymarket Global / Polymarket US sports moneylines"
    )
    parser.add_argument("--write", action="store_true", help="Write matchedtable.csv and match_review.csv")
    parser.add_argument("--sport", type=str, default=None, help="Optional sport/league filter (e.g. mlb)")
    parser.add_argument("--no-ai", action="store_true", help="Skip AI verifier; ambiguous -> review only")
    parser.add_argument("--matched-path", type=Path, default=DEFAULT_MATCHED_PATH)
    parser.add_argument("--review-path", type=Path, default=DEFAULT_REVIEW_PATH)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    setup_logging(verbose=args.verbose)
    result = run_match(sport=args.sport, use_ai=not args.no_ai)

    logging.info(
        "Result summary: accepted=%s review=%s",
        len(result.accepted),
        len(result.review),
    )
    venue_counts: dict[str, int] = {}
    for decision in result.accepted:
        c = decision.candidate
        pair = f"{c.leg_a.exchange}|{c.leg_b.exchange}"
        venue_counts[pair] = venue_counts.get(pair, 0) + 1
    logging.info("Accepted by venue pair: %s", venue_counts)

    for decision in result.accepted[:20]:
        c = decision.candidate
        logging.info(
            "ACCEPT %s | %s %s (%s) | %s %s (%s) | %s",
            c.leg_a.league or c.leg_b.league,
            c.leg_a.exchange,
            c.leg_a.outcome_team,
            c.leg_a.exchange_id[:48],
            c.leg_b.exchange,
            c.leg_b.outcome_team,
            c.leg_b.exchange_id[:48],
            decision.source,
        )
    if len(result.accepted) > 20:
        logging.info("... %s more accepted", len(result.accepted) - 20)

    if args.write:
        write_match_outputs(
            result,
            matched_path=args.matched_path,
            review_path=args.review_path,
        )
    else:
        logging.info("Dry-run only. Re-run with --write to update %s", args.matched_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
