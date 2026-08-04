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
    "pair_id",
    "market_desc",
    "exchange_a",
    "exchange_b",
    "ticker_a",
    "ticker_b",
    "side_a",
    "side_b",
    "game_status",
    "ask_a",
    "ask_b",
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
    One plain-data sample of a matched complementary pair.

    Build this from whatever source you have (live books, historical ticks, etc.).
    The logger never touches orderbook objects directly.
    """

    pair_id: str
    exchange_a: str
    exchange_b: str
    ticker_a: str
    ticker_b: str
    ask_a: Optional[float]
    ask_b: Optional[float]
    ask_a_volume: float = 0.0
    ask_b_volume: float = 0.0
    side_a: str = ""
    side_b: str = ""
    market_desc: str = ""
    game_status: str = "unknown"
    # Net spread after fees; if None, only raw gap (1 - asks) is used for open/close.
    net_spread: Optional[float] = None
    timestamp: Optional[datetime] = None
    # Minimum net spread required to treat the gap as open (matches StrategyEngine.MIN_NET_SPREAD).
    min_net_spread: float = 0.01

    @property
    def pair_key(self) -> str:
        return self.pair_id or f"{self.exchange_a}:{self.ticker_a}|{self.exchange_b}:{self.ticker_b}"

    @property
    def raw_gap(self) -> Optional[float]:
        if self.ask_a is None or self.ask_b is None:
            return None
        return 1.0 - self.ask_a - self.ask_b

    @property
    def available_volume(self) -> float:
        return min(self.ask_a_volume, self.ask_b_volume)

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
            "pair_id": self.pair_id,
            "market_desc": self.market_desc,
            "exchange_a": self.exchange_a,
            "exchange_b": self.exchange_b,
            "ticker_a": self.ticker_a,
            "ticker_b": self.ticker_b,
            "side_a": self.side_a,
            "side_b": self.side_b,
            "game_status": self.game_status,
            "ask_a": self.ask_a if self.ask_a is not None else "",
            "ask_b": self.ask_b if self.ask_b is not None else "",
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
            pair_id="1", exchange_a="kalshi", exchange_b="poly_global",
            ticker_a="...", ticker_b="...", ask_a=0.42, ask_b=0.51,
            ask_a_volume=20, ask_b_volume=15, market_desc="Dodgers vs Astros",
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
