from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.state_classes.arb_group import ArbGroup
from src.state_classes.arb_pair import ArbPair
from src.state_classes.exchange_legs import KalshiLeg, Leg, PolymarketUsLeg
from src.state_classes.orderbook import Orderbook
from src.util.enums import Exchange


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MATCHED_TABLE_PATH = PROJECT_ROOT / "data" / "matchedtable.csv"


class ArbHolder:
    _instance = None
    _initialized = False
    arb_groups: dict = {}
    arb_pairs: dict = {}

    def __new__(cls, *args, **kwargs):
        """
        Return the shared ArbHolder instance so all components see the same books and mappings.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """
        Load matched markets once and initialize empty Kalshi/Polymarket orderbooks plus lookup maps.
        """
        if self._initialized:
            return
        self.arb_groups = {}
        self.arb_pairs = {}
        matched_df = pd.read_csv(MATCHED_TABLE_PATH)
        for _, row in matched_df.iterrows():
            self.process_row(row)
        self._initialized = True

    """
    group_id,pair_id,enabled,
    exchange_a,ticker_a,outcome_a,
    side_id_a,order_intent_a,
    exchange_b,ticker_b,outcome_b,side_id_b,order_intent_b,
    market_desc
    """

    def process_row(self, row: pd.Series) -> None:
        group_id = row.get("group_id")
        pair_id = str(row.get("pair_id", "") or "").strip()
        description = str(row.get("market_desc", "") or "").strip()

        leg_a = self.create_leg(
            exchange=row.get("exchange_a"),
            ticker=row.get("ticker_a"),
            outcome=row.get("outcome_a"),
            side=row.get("side_id_a"),
            order_intent=row.get("order_intent_a"),
            description=description,
        )
        leg_b = self.create_leg(
            exchange=row.get("exchange_b"),
            ticker=row.get("ticker_b"),
            outcome=row.get("outcome_b"),
            side=row.get("side_id_b"),
            order_intent=row.get("order_intent_b"),
            description=description,
        )
        legs = [leg for leg in (leg_a, leg_b) if leg is not None]
        if len(legs) != 2 or not pair_id:
            return

        pair = ArbPair(
            pair_id=pair_id,
            description=description,
            legs=legs,
            group_id=None if pd.isna(group_id) else str(group_id),
        )
        self.arb_pairs[pair_id] = pair

        if pair.group_id:
            group = self.arb_groups.get(pair.group_id)
            if group is None:
                group = ArbGroup(group_id=pair.group_id, label=description)
                self.arb_groups[pair.group_id] = group
            group.arb_pairs.append(pair)

    def create_leg(
        self,
        exchange,
        ticker,
        outcome,
        side=None,
        order_intent=None,
        description: str = "",
    ) -> Leg | None:
        side_s = self._clean_id(side)
        intent_s = self._clean_id(order_intent)
        ticker_s = self._clean_id(ticker)
        if not ticker_s:
            return None
        outcome_s = self._clean_id(outcome) or ""

        exchange_tag = self._normalize_exchange(exchange)
        book = Orderbook()

        if exchange_tag == "kalshi":
            return KalshiLeg(
                exchange=Exchange.KALSHI,
                description=description or outcome_s,
                orderbook=book,
                est_start_date=None,
                est_end_date=None,
                expiration_time=None,
                market_ticker=ticker_s,
                outcome_key=outcome_s,
            )
        if exchange_tag == "poly_us":
            return PolymarketUsLeg(
                exchange=Exchange.POLYMARKET_US,
                description=description or outcome_s,
                orderbook=book,
                est_start_date=None,
                est_end_date=None,
                expiration_time=None,
                market_slug=ticker_s,
                side_id=side_s,
                outcome_key=outcome_s,
                order_intent=intent_s,
            )
        return None

    @staticmethod
    def _clean_id(value) -> str | None:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        if isinstance(value, int):
            return str(value)
        text = str(value).strip()
        if not text or text.lower() == "nan":
            return None
        if text.endswith(".0") and text[:-2].isdigit():
            return text[:-2]
        return text

    @staticmethod
    def _normalize_exchange(value) -> str:
        tag = str(value or "").strip().lower()
        aliases = {
            "kalshi": "kalshi",
            "poly_us": "poly_us",
            "polymarket_us": "poly_us",
            "polymarket": "poly_us",
        }
        return aliases.get(tag, tag)
