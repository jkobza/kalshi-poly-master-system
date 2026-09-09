from collections import defaultdict
from pathlib import Path

import pandas as pd

from src.state_classes.orderbook import Orderbook
from src.state_classes.arb_pair import ArbPair
from src.state_classes.arb_group import ArbGroup
from src.state_classes.outcome_leg import OutcomeLeg
from src.util.enums import Exchange


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MATCHED_TABLE_PATH = PROJECT_ROOT / "data" / "matchedtable.csv"


class ArbHolder:
    _instance = None
    _initialized = False
    arb_groups = {}
    arb_pairs = {}


    def __new__(self, *args, **kwargs):
        """
        Return the shared MarketHolder instance so all components see the same books and mappings.
        """
        if self._instance is None:
            self._instance = super(ArbHolder, self).__new__(self)
        return self._instance

    def __init__(self):
        """
        Load matched markets once and initialize empty Kalshi/Polymarket orderbooks plus lookup maps.
        """
        matched_df = pd.read_csv(MATCHED_TABLE_PATH)
        for _,row in matched_df.iterrows():
            self.create_outcome_legs_from_row(row)


    '''
    group_id,pair_id,enabled,
    exchange_a,ticker_a,outcome_a,
    side_id_a,order_intent_a,
    exchange_b,ticker_b,outcome_b,side_id_b,order_intent_b,
    market_desc
'''


    def process_row(self,row: pd.DataFrame):
        group_id = row['group_id']
        pair_id = row['pair_id']
        # if group_id not in self.arb_groups:
        #     self.arb_groups[group_id] = ArbGroup()
        # if pair_id not in self.arb_pairs:
        #     self.arb_pairs[pair_id] = ArbPair()
        exchange_a = row['exchange_a']
        ticker_a = row['ticker_a']
        outcome_a = row['outcome_a']
        side_id_a = row['side_id_a']
        order_intent_a = row['order_intent_a']
        leg_a = self.create_outcome_leg(group_id, pair_id,exchange_a, ticker_a, outcome_a, side_id_a, order_intent_a)

    def create_outcome_leg(self, group_id, pair_id, exchange, ticker, outcome, side, order_intent):
        if pd.isna(side):
            side = None
        if pd.isna(order_intent):
            order_intent = None
        leg = OutcomeLeg(exchange=exchange, ticker=ticker, outcome_key=outcome, oderbook=Orderbook(),side=side, order_intent=order_intent)