from __future__ import annotations

from pathlib import Path
import csv
import pandas as pd
from datetime import datetime

from src.state_classes.arb_pair import ArbPair
from src.state_classes.exchange_legs import KalshiLeg, Leg, PolymarketUsLeg
from src.state_classes.orderbook import Orderbook
from src.util.enums import Exchange


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MATCHED_TABLE_PATH = PROJECT_ROOT / "data" / "matchedtable.csv"
KALSHI_TABLE_PATH = PROJECT_ROOT /"data"/"kalshi_markets.csv"
PMUS_TABLE_PATH = PROJECT_ROOT/"data"/"polymarket_us_markets.csv"

class ArbHolder:
    """Hold matched arb pairs for for the univer."""

    # Add additonal markets here later

    def __init__(self):
        # Dict of Kalshi
        self.legs_by_id = {}
        self.books_by_market = {}
        self.arb_pairs_by_pairid = {}
        self.arb_pairs_by_leg = {}
        self.legs_by_id = {}



    """id,market_ticker,outcome_side,est_start_date,est_end_date,expiration_time"""
    def process_kalshi_markets_table(self):

    # Track all outcomes we have see for kalshi, so that duplicates are omitted
        seen_outcomes = {
    (leg.market_ticker, leg.outcome_side)
    for leg in self.legs_by_id.values()
    if leg.exchange == Exchange.KALSHI
        }

        with KALSHI_TABLE_PATH.open(newline="", encoding="utf-8") as file:
            for line_number, row in enumerate(csv.DictReader(file), start=2):
                try:

                    k_id = row["k_id"].strip()
                    market_ticker = row["market_ticker"].strip()
                    outcome_side=row["outcome_side"].strip().lower()
                    
                    # Ensure k_id, market_ticker, outcome_side are unique and not missing
                    if not k_id:
                        raise ValueError("k_id is empty")
                    if k_id in self.kalshi_markets:
                        raise ValueError(f"Duplicate k_id: {k_id!r}")
                    if not market_ticker:
                        raise ValueError("market_ticker is empty")
                    if outcome_side not in {"yes", "no"}:
                        raise ValueError(f"Invalid outcome_side: {outcome_side!r}")

                    outcome_key = (market_ticker, outcome_side)
                    if outcome_key in seen_outcomes:
                        raise ValueError(f"Duplicate market/outcome: {outcome_key}")

                    est_start_date = parse_datetime(row["est_start_date"])
                    est_end_date = parse_datetime(row["est_end_date"])
                    expiration_time = parse_datetime(row["expiration_time"])
                    description = row["description"].strip()

                    market_key = (Exchange.KALSHI, market_ticker)

                    if market_key not in self.books_by_market:
                        self.books_by_market[market_key] = Orderbook()

                    book = self.books_by_market[market_key]

                    leg = KalshiLeg(k_id,exchange=Exchange.KALSHI, description=description,orderbook = book,
                                    est_start_date=est_start_date,est_end_date=est_end_date, 
                                    expiration_time=expiration_time,market_ticker=market_ticker,
                                    outcome_side=outcome_side
                                    )

                    self.legs_by_id[k_id] = leg
                    seen_outcomes.add(outcome_key)

                except ValueError as exc:
                    raise ValueError(
                        f"{KALSHI_TABLE_PATH.name}, row {line_number}: {exc}"
                    ) from exc

    def process_pmus_markets_table(self):
        # Track all outcomes we have see for kalshi, so that duplicates are omitted
                seen_outcomes = {
                    (leg.market_ticker, leg.outcome_side)
                    for leg in self.legs_by_id.values()
                    if leg.exchange == Exchange.POLYMARKET_US
                        }
        
                with PMUS_TABLE_PATH.open(newline="", encoding="utf-8") as file:
                    for line_number, row in enumerate(csv.DictReader(file), start=2):
                        try:
        
                            p_id = row["p_id"].strip()
                            market_ticker = row["market_ticker"].strip()
                            outcome_side=row["outcome_side"].strip().lower()
                            
                            # Ensure k_id, market_ticker, outcome_side are unique and not missing
                            if not p_id:
                                raise ValueError("k_id is empty")
                            if p_id in self.pmus_markets:
                                raise ValueError(f"Duplicate k_id: {p_id!r}")
                            if not market_ticker:
                                raise ValueError("market_ticker is empty")
                            if outcome_side not in {"yes", "no"}:
                                raise ValueError(f"Invalid outcome_side: {outcome_side!r}")
        
                            outcome_key = (market_ticker, outcome_side)
                            if outcome_key in seen_outcomes:
                                raise ValueError(f"Duplicate market/outcome: {outcome_key}")
        
                            est_start_date = parse_datetime(row["est_start_date"])
                            est_end_date = parse_datetime(row["est_end_date"])
                            expiration_time = parse_datetime(row["expiration_time"])
                            description = row["description"].strip()

                            market_key = (Exchange.POLYMARKET_US, market_ticker)

                            if market_key not in self.books_by_market:
                                self.books_by_market[market_key] = Orderbook()

                            book = self.books_by_market[market_key]

                            leg = PolymarketUsLeg(p_id,exchange=Exchange.POLYMARKET_US, description=description,orderbook = book,
                                            est_start_date=est_start_date,est_end_date=est_end_date, 
                                            expiration_time=expiration_time,market_ticker=market_ticker,
                                            outcome_side=outcome_side
                                            )
        
                            self.legs_by_id[p_id] = leg
                            seen_outcomes.add(outcome_key)
        
                        except ValueError as exc:
                            raise ValueError(
                                f"{PMUS_TABLE_PATH.name}, row {line_number}: {exc}"
                            ) from exc

    def process_matchedtable(self):
        with MATCHED_TABLE_PATH.open(newline="", encoding="utf-8") as file:
                for line_number, row in enumerate(csv.DictReader(file), start=2):
                    try:
                        '''pair_id,description,leg1_id,leg2_id'''
                        pair_id = row["pair_id"]
                        description = row["description"]
                        leg1_id = row["leg1_id"]
                        leg2_id = row["leg2_id"]

                        if pair_id in self.arb_pairs_by_pairid:
                            raise ValueError(f"Duplicate pairid {pair_id}")

                        if leg1_id == leg2_id:
                            raise ValueError(f"Duplicate Legs in Table")

                        if not leg1_id in self.legs_by_id:
                            raise ValueError(f"Leg not Found {leg1_id}")

                        if not leg2_id in self.legs_by_id:
                            raise ValueError(f"Leg not found {leg2_id}")

                        leg1 = self.legs_by_id[leg1_id]
                        leg2 = self.legs_by_id[leg2_id]

                        # Legs should have same start and end time roughly. 

                        pair = ArbPair(pair_id=pair_id, description=description,
                                       legs=[leg1, leg2])
                        self.arb_pairs_by_pairid[pair_id] = pair
                        for leg in pair.legs:
                            self.arb_pairs_by_leg.setdefault(leg.leg_id, set()).add(pair_id)
                    except ValueError as exc:
                        raise ValueError(
                            f"{KALSHI_TABLE_PATH.name}, row {line_number}: {exc}"
                            ) from exc

                                
                                     

    def load(self):
        self.process_kalshi_markets_table()
        self.process_pmus_markets_table()
        self.process_matchedtable()

def parse_datetime(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include a timezone: {value!r}")
    return parsed
