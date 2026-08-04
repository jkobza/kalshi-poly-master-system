"""
Write matchedtable.csv and match_review.csv outputs.
"""

from __future__ import annotations

import csv
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from src.matching.models import MatchDecision, MatchResult

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MATCHED_PATH = PROJECT_ROOT / "data" / "matchedtable.csv"
DEFAULT_REVIEW_PATH = PROJECT_ROOT / "data" / "match_review.csv"

MATCHED_FIELDS = [
    "pair_id",
    "exchange_a",
    "exchange_b",
    "ticker_a",
    "ticker_b",
    "side_a",
    "side_b",
    "market_desc",
]
REVIEW_FIELDS = [
    "timestamp_utc",
    "accepted",
    "confidence",
    "source",
    "score",
    "detail",
    "exchange_a",
    "exchange_b",
    "ticker_a",
    "ticker_b",
    "side_a",
    "side_b",
    "title_a",
    "title_b",
    "league",
    "date_a",
    "date_b",
    "reason",
]


def _desc(decision: MatchDecision) -> str:
    c = decision.candidate
    a, b = c.leg_a, c.leg_b
    day = a.start_date or b.start_date or ""
    return (
        f"{a.outcome_team} {a.exchange} - {b.outcome_team} {b.exchange} "
        f"({a.league or b.league} {day})"
    ).strip()


def matched_rows(decisions: list[MatchDecision]) -> list[dict]:
    rows = []
    for idx, decision in enumerate(decisions, start=1):
        c = decision.candidate
        a, b = c.leg_a, c.leg_b
        rows.append(
            {
                "pair_id": str(idx),
                "exchange_a": a.exchange,
                "exchange_b": b.exchange,
                "ticker_a": a.exchange_id,
                "ticker_b": b.exchange_id,
                "side_a": a.outcome_team,
                "side_b": b.outcome_team,
                "market_desc": _desc(decision),
            }
        )
    return rows


def review_rows(decisions: list[MatchDecision]) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for decision in decisions:
        c = decision.candidate
        a, b = c.leg_a, c.leg_b
        rows.append(
            {
                "timestamp_utc": now,
                "accepted": decision.accepted,
                "confidence": decision.confidence,
                "source": decision.source,
                "score": c.score,
                "detail": decision.detail,
                "exchange_a": a.exchange,
                "exchange_b": b.exchange,
                "ticker_a": a.exchange_id,
                "ticker_b": b.exchange_id,
                "side_a": a.outcome_team,
                "side_b": b.outcome_team,
                "title_a": a.title,
                "title_b": b.title,
                "league": a.league or b.league,
                "date_a": a.start_date.isoformat() if a.start_date else "",
                "date_b": b.start_date.isoformat() if b.start_date else "",
                "reason": c.reason,
            }
        )
    return rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def write_match_outputs(
    result: MatchResult,
    matched_path: Path = DEFAULT_MATCHED_PATH,
    review_path: Path = DEFAULT_REVIEW_PATH,
    backup: bool = True,
) -> None:
    """
    Overwrite matchedtable with accepted rows; write full review queue.
    """
    if backup and matched_path.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = matched_path.with_name(f"matchedtable.backup.{stamp}.csv")
        shutil.copy2(matched_path, backup_path)
        logging.info("Backed up previous matched table to %s", backup_path)

    write_csv(matched_path, MATCHED_FIELDS, matched_rows(result.accepted))
    write_csv(review_path, REVIEW_FIELDS, review_rows(result.review))
    logging.info(
        "Wrote %s accepted pairs to %s and %s review rows to %s",
        len(result.accepted),
        matched_path,
        len(result.review),
        review_path,
    )
