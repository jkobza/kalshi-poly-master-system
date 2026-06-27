from collections import defaultdict
from pathlib import Path

import pandas as pd

from src.state_classes.orderbook import Orderbook
from src.util.enums import Exchange


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MATCHED_TABLE_PATH = PROJECT_ROOT / "data" / "matchedtable.csv"


class MarketHolder:
    _instance = None
    _initialized = False


    def __new__(self, *args, **kwargs):
        """
        Return the shared MarketHolder instance so all components see the same books and mappings.
        """
        if self._instance is None:
            self._instance = super(MarketHolder, self).__new__(self)
        return self._instance

    def __init__(self):
        """
        Load matched markets once and initialize empty Kalshi/Polymarket orderbooks plus lookup maps.
        """
        if self._initialized:
            return
        self.kalshi_orderbooks: dict[str, Orderbook] = {}
        self.poly_orderbooks: dict[str, Orderbook] = {}
        self.p_to_k_map: defaultdict[str, list[str]] = defaultdict(list)
        self.k_to_p_map: defaultdict[str, list[str]] = defaultdict(list)
        df = pd.read_csv(MATCHED_TABLE_PATH)
        print(df)
        for index, row in df.iterrows():
            poly_id = str(row['poly_id']).strip()
            kalshi_id = str(row['kalshi_id']).strip()
            if kalshi_id not in self.kalshi_orderbooks:
                self.kalshi_orderbooks[kalshi_id] = Orderbook()

            if poly_id not in self.poly_orderbooks:
                self.poly_orderbooks[poly_id] = Orderbook()
                # Build the relational maps
            self.k_to_p_map[kalshi_id].append(poly_id)
            self.p_to_k_map[poly_id].append(kalshi_id)
        self._initialized = True

    def get_orderbook(self, exchange: Exchange, asset_id: str) -> Orderbook | None:
        """
        Return the stored orderbook for an exchange/asset pair, or None for an unsupported exchange.
        """
        if exchange == Exchange.KALSHI:
            return self.kalshi_orderbooks[asset_id]
        elif exchange == Exchange.POLYMARKET:
            return self.poly_orderbooks[asset_id]
        else:
            return None;
