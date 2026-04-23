from collections import defaultdict
from src.state_classes import orderbook
import pandas as pd

from src.state_classes.orderbook import Orderbook


class MarketHolder:
    _instance = None
    _initialized = False


    def __new__(self, *args, **kwargs):
        if self._instance is None:
            self._instance = super(MarketHolder, self).__new__(self)
        return self._instance

    def __init__(self):
        '''
        :var kalshi_orderbooks: a Dictionary  mapping
        '''
        if self._initialized:
            return
        self.kalshi_orderbooks: dict[str, Orderbook] = {}
        self.poly_orderbooks: dict[str, Orderbook] = {}
        defaultdict[str, list[str]] = defaultdict(list)
        self.p_to_k_map: defaultdict[str, list[str]] = defaultdict(list)
        df = pd.read_csv('../../data/matchedtable.csv')
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

