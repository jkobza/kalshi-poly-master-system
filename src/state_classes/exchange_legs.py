from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.state_classes.orderbook import Orderbook
from src.util.enums import Exchange


@dataclass
class Leg:
    """
    One tradeable outcome on a single venue, identified by its CSV leg ID.
    """

    leg_id: str
    exchange: Exchange
    description: str
    orderbook: Orderbook
    est_start_date: datetime | None
    est_end_date: datetime | None
    expiration_time: datetime | None
    

@dataclass
class KalshiLeg(Leg):
    """Kalshi markets are addressed by market ticker."""

    market_ticker: str
    outcome_side: str

    def __post_init__(self) -> None:
        self.exchange = Exchange.KALSHI

    @property
    def leg_info(self) -> tuple[str,str]:
        return self.market_ticker, self.outcome_side


@dataclass
class PolymarketUsLeg(Leg):
    """Polymarket US markets need a market slug plus outcome side."""

    market_ticker: str
    outcome_side: str

    def __post_init__(self) -> None:
        self.exchange = Exchange.POLYMARKET_US

    @property
    def leg_info(self) -> str:
        return self.market_slug, self.outcome_side
