"""
Arbitrage opportunity CSV logger built on the generic gap tracker.

Accepts plain price/volume snapshots — no orderbook or engine imports — so it can
be driven from the live strategy, a dry-run monitor, notebooks, or tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.monitoring.csv_writer import CsvEventWriter
from src.monitoring.gap_tracker import GapEvent, GapObservation, GapTracker, utc_now


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OPPORTUNITY_LOG_PATH = PROJECT_ROOT / "logs" / "opportunities.csv"

OPPORTUNITY_LOG_FIELDS = [
    "timestamp_utc",
    "event",
    "gap_id",
    "market_desc",
    "kalshi_id",
    "poly_id",
    "game_status",
    "kalshi_ask",
    "poly_ask",
    "raw_gap",
    "net_spread",
    "available_volume",
    "potential_win_per_contract",
    "potential_win_total",
    "gap_opened_at_utc",
    "duration_seconds",
]


@dataclass
class OpportunitySnapshot:
    """
    One plain-data sample of a matched Kalshi/Polymarket pair.

    Build this from whatever source you have (live books, historical ticks, etc.).
    The logger never touches orderbook objects directly.
    """

    kalshi_id: str
    poly_id: str
    kalshi_ask: Optional[float]
    poly_ask: Optional[float]
    kalshi_ask_volume: float = 0.0
    poly_ask_volume: float = 0.0
    market_desc: str = ""
    game_status: str = "unknown"
    # Net spread after fees; if None, only raw gap (1 - asks) is used for open/close.
    net_spread: Optional[float] = None
    timestamp: Optional[datetime] = None
    # Minimum net spread required to treat the gap as open (matches StrategyEngine.MIN_NET_SPREAD).
    min_net_spread: float = 0.01

    @property
    def pair_key(self) -> str:
        return f"{self.kalshi_id}|{self.poly_id}"

    @property
    def raw_gap(self) -> Optional[float]:
        if self.kalshi_ask is None or self.poly_ask is None:
            return None
        return 1.0 - self.kalshi_ask - self.poly_ask

    @property
    def available_volume(self) -> float:
        return min(self.kalshi_ask_volume, self.poly_ask_volume)

    @property
    def is_gap_open(self) -> bool:
        raw = self.raw_gap
        if raw is None or raw <= 0:
            return False
        if self.net_spread is None:
            return raw > self.min_net_spread
        return self.net_spread > self.min_net_spread

    @property
    def potential_win_per_contract(self) -> Optional[float]:
        if self.net_spread is not None:
            return self.net_spread
        return self.raw_gap

    @property
    def potential_win_total(self) -> Optional[float]:
        per = self.potential_win_per_contract
        if per is None:
            return None
        return per * self.available_volume

    def to_payload(self) -> dict:
        return {
            "market_desc": self.market_desc,
            "kalshi_id": self.kalshi_id,
            "poly_id": self.poly_id,
            "game_status": self.game_status,
            "kalshi_ask": self.kalshi_ask if self.kalshi_ask is not None else "",
            "poly_ask": self.poly_ask if self.poly_ask is not None else "",
            "raw_gap": self.raw_gap if self.raw_gap is not None else "",
            "net_spread": self.net_spread if self.net_spread is not None else "",
            "available_volume": self.available_volume,
            "potential_win_per_contract": (
                self.potential_win_per_contract if self.potential_win_per_contract is not None else ""
            ),
            "potential_win_total": (
                self.potential_win_total if self.potential_win_total is not None else ""
            ),
        }


class OpportunityLogger:
    """
    Track arbitrage gaps and append lifecycle rows to a CSV file.

    Example (from any caller that already has prices):

        logger = OpportunityLogger()
        logger.observe(OpportunitySnapshot(
            kalshi_id="...", poly_id="...", kalshi_ask=0.42, poly_ask=0.51,
            kalshi_ask_volume=20, poly_ask_volume=15, market_desc="Dodgers vs Astros",
            game_status="active", net_spread=0.05,
        ))
    """

    def __init__(
        self,
        path: Path | None = None,
        update_on_change_only: bool = True,
        writer: CsvEventWriter | None = None,
        tracker: GapTracker | None = None,
    ):
        self.path = Path(path) if path is not None else DEFAULT_OPPORTUNITY_LOG_PATH
        self.writer = writer or CsvEventWriter(self.path, OPPORTUNITY_LOG_FIELDS)
        self.tracker = tracker or GapTracker(update_on_change_only=update_on_change_only)

    def observe(self, snapshot: OpportunitySnapshot) -> Optional[GapEvent]:
        """
        Ingest one pair snapshot. Writes a CSV row when a gap opens, meaningfully
        updates, or closes. Returns the emitted event, or None if nothing was logged.
        """
        timestamp = snapshot.timestamp or utc_now()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        event = self.tracker.observe(
            GapObservation(
                key=snapshot.pair_key,
                is_open=snapshot.is_gap_open,
                timestamp=timestamp,
                payload=snapshot.to_payload(),
            )
        )
        if event is not None:
            self._write_event(event)
        return event

    def _write_event(self, event: GapEvent) -> None:
        row = {
            "timestamp_utc": event.timestamp.isoformat(),
            "event": event.event,
            "gap_id": event.gap_id,
            "gap_opened_at_utc": event.opened_at.isoformat(),
            "duration_seconds": round(event.duration_seconds, 3),
            **event.payload,
        }
        self.writer.append(row)
