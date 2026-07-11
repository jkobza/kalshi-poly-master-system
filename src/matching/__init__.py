"""
Sports market matching: discover, normalize, and pair Kalshi/Polymarket moneylines.
"""

from src.matching.models import (
    MatchCandidate,
    MatchDecision,
    MatchResult,
    NormalizedOutcome,
)

__all__ = [
    "MatchCandidate",
    "MatchDecision",
    "MatchResult",
    "NormalizedOutcome",
]
