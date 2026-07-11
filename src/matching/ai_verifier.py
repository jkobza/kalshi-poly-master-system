"""
Optional LLM verifier for ambiguous Kalshi/Polymarket market pairs.

If OPENAI_API_KEY is unset, all ambiguous candidates are sent to review unchanged.
Unsure / non-high answers never auto-accept.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

import requests

from src.matching.models import MatchCandidate, MatchDecision


def _api_key() -> Optional[str]:
    return os.getenv("OPENAI_API_KEY") or os.getenv("MATCHER_OPENAI_API_KEY")


def _candidate_payload(candidate: MatchCandidate) -> dict:
    p, k = candidate.poly, candidate.kalshi
    return {
        "polymarket": {
            "title": p.title,
            "league": p.league,
            "date": p.start_date.isoformat() if p.start_date else None,
            "teams": [p.team_a, p.team_b],
            "outcome_team": p.outcome_team,
            "token_id": p.exchange_id,
            "market_type": p.market_type,
        },
        "kalshi": {
            "title": k.title,
            "league": k.league,
            "date": k.start_date.isoformat() if k.start_date else None,
            "teams": [k.team_a, k.team_b],
            "outcome_team": k.outcome_team,
            "ticker": k.exchange_id,
            "market_type": k.market_type,
        },
        "deterministic_score": candidate.score,
        "deterministic_reason": candidate.reason,
        "note": (
            "These would be paired as opposite-side moneyline outcomes for arbitrage "
            "(Polymarket pays on one team, Kalshi on the other). "
            "Confirm they refer to the SAME underlying game and are moneyline winner markets."
        ),
    }


def verify_candidate(candidate: MatchCandidate, timeout: float = 45.0) -> MatchDecision:
    """
    Ask the LLM whether the candidate is the same market.

    Accept only when same_market is true AND confidence is high.
    Anything else goes to review (accepted=False).
    """
    key = _api_key()
    if not key:
        return MatchDecision(
            candidate=candidate,
            accepted=False,
            confidence="medium",
            source="rejected",
            detail="ai_unavailable:" + candidate.reason,
        )

    payload = _candidate_payload(candidate)
    system = (
        "You verify whether two sports betting markets on different exchanges refer to the "
        "same underlying moneyline game. Reply with ONLY compact JSON: "
        '{"same_market": true|false|null, "confidence": "high"|"medium"|"low", "reason": "..."}. '
        "Use same_market=null and confidence=low when unsure. "
        "Reject spreads, totals, props, parlays, or different games/dates."
    )
    body = {
        "model": os.getenv("MATCHER_OPENAI_MODEL", "gpt-4o-mini"),
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload)},
        ],
    }
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=timeout,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = _extract_json(content)
        same = parsed.get("same_market")
        confidence = str(parsed.get("confidence") or "low").lower()
        reason = str(parsed.get("reason") or content)[:500]
        if same is True and confidence == "high":
            return MatchDecision(
                candidate=candidate,
                accepted=True,
                confidence="high",
                source="ai",
                detail=reason,
            )
        return MatchDecision(
            candidate=candidate,
            accepted=False,
            confidence="medium" if confidence == "medium" else "low",
            source="rejected",
            detail=f"ai:{same}/{confidence}:{reason}",
        )
    except Exception as exc:
        logging.exception("AI verifier failed")
        return MatchDecision(
            candidate=candidate,
            accepted=False,
            confidence="low",
            source="rejected",
            detail=f"ai_error:{exc}",
        )


def verify_ambiguous(candidates: list[MatchCandidate]) -> list[MatchDecision]:
    return [verify_candidate(c) for c in candidates]


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise
