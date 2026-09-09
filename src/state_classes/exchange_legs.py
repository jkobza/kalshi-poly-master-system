from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from src.state_classes.orderbook import Orderbook
from src.util.enums import Exchange


@dataclass
class Leg(ABC):
    """
    One tradeable outcome on a single venue.

    Pair-level metadata (pair_id, shared desc/times) lives on ArbPair, not here.
    """

    exchange: Exchange
    description: str
    orderbook: Orderbook
    est_start_date: datetime | None
    est_end_date: datetime | None
    expiration_time: datetime | None

    @property
    @abstractmethod
    def asset_id(self) -> str:
        """Venue-native id used for WS subscribe / orderbook map / orders."""


@dataclass
class KalshiLeg(Leg):
    """Kalshi markets are addressed by market ticker."""

    market_ticker: str
    outcome_key: str

    def __post_init__(self) -> None:
        self.exchange = Exchange.KALSHI

    @property
    def asset_id(self) -> str:
        return self.market_ticker


@dataclass
class PolymarketUsLeg(Leg):
    """Polymarket US markets need a market slug plus side (and optional order intent)."""

    market_slug: str
    side_id: str | None
    outcome_key: str
    order_intent: str | None

    def __post_init__(self) -> None:
        self.exchange = Exchange.POLYMARKET_US

    @property
    def asset_id(self) -> str:
        if self.side_id:
            return self.side_id
        return f"{self.market_slug}:{self.outcome_key.lower()}"
