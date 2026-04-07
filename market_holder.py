from collections import defaultdict
import orderbook as book
import pandas as pd

class MarketHolder:
    _instance = None
    _initialized = False


    def __new__(self, *args, **kwargs):
        if self._instance is None:
            self._instance = super(MarketHolder, self).__new__(self)
        return self._instance

    def __init__(self):
        if self._initialized:
            return
        self.kalshi_orderbooks = {}
        self.poly_orderbooks = {}
        self.k_to_p_map = defaultdict(list)
        self.p_to_k_map = defaultdict(list)
        df = pd.read_csv('data/matchedtable.csv')
        print(df)
        for index, row in df.iterrows():
            poly_id = row['poly_id']
            kalshi_id = row['kalshi_id']
            if kalshi_id not in self.kalshi_orderbooks:
                self.kalshi_orderbooks[kalshi_id] = book.Orderbook()

            if poly_id not in self.poly_orderbooks:
                self.poly_orderbooks[poly_id] = book.Orderbook()
                # Build the relational maps
            self.k_to_p_map[kalshi_id].append(poly_id)
            self.p_to_k_map[poly_id].append(kalshi_id)
        self._initialized = True

