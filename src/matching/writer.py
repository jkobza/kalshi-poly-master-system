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

MATCHED_FIELDS = ["market_id", "poly_id", "kalshi_id", "market_desc"]
REVIEW_FIELDS = [
    "timestamp_utc",
    "accepted",
    "confidence",
    "source",
    "score",
    "detail",
    "poly_id",
    "kalshi_id",
    "poly_title",
    "kalshi_title",
    "league",
    "poly_date",
    "kalshi_date",
    "poly_outcome",
    "kalshi_outcome",
    "reason",
]


def _desc(decision: MatchDecision) -> str:
    c = decision.candidate
    return (
        f"{c.poly.outcome_team} Polymarket - {c.kalshi.outcome_team} Kalshi "
        f"({c.poly.league} {c.poly.start_date or c.kalshi.start_date or ''})"
    ).strip()


def matched_rows(decisions: list[MatchDecision]) -> list[dict]:
    rows = []
    for idx, decision in enumerate(decisions, start=1):
        c = decision.candidate
        rows.append(
            {
                "market_id": str(idx),
                "poly_id": c.poly.exchange_id,
                "kalshi_id": c.kalshi.exchange_id,
                "market_desc": _desc(decision),
            }
        )
    return rows


def review_rows(decisions: list[MatchDecision]) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for decision in decisions:
        c = decision.candidate
        rows.append(
            {
                "timestamp_utc": now,
                "accepted": decision.accepted,
                "confidence": decision.confidence,
                "source": decision.source,
                "score": c.score,
                "detail": decision.detail,
                "poly_id": c.poly.exchange_id,
                "kalshi_id": c.kalshi.exchange_id,
                "poly_title": c.poly.title,
                "kalshi_title": c.kalshi.title,
                "league": c.poly.league or c.kalshi.league,
                "poly_date": c.poly.start_date.isoformat() if c.poly.start_date else "",
                "kalshi_date": c.kalshi.start_date.isoformat() if c.kalshi.start_date else "",
                "poly_outcome": c.poly.outcome_team,
                "kalshi_outcome": c.kalshi.outcome_team,
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
