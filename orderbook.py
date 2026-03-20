import bisect

class Orderbook:
    def __init__(self):
            self.bidPrices =  []
            self.bidVolumes =  {}
            self.askPrices = []
            self.askVolumes = {}

    def _update_book(self, prices, volumes, price, volume):
        if volume > 0:
            if price not in volumes:
                bisect.insort(prices, price)
            volumes[price] = volume

        else: #volume is 0 or neg
            if price in volumes:
                del volumes[price]
                # log n search and delete
                index = bisect.bisect_left(prices, price)
                if index < len(prices) and prices[index] == price:
                    prices.pop(index)


    def process_bid(self, order, price, volume):
        """
        Adds a bid to the particular orderbook.
        """
        self._update_book(self.bidPrices, self.bidVolumes, price, volume)


    def process_ask(self, order, price, volume):
        self._update_book(self.askPrices, self.askVolumes, price, volume)

    def best_bid(self):
        if not self.bidPrices: return None
        price = self.bidPrices[-1]
        return {"bid":price, "volume":self.bidVolumes[price]}

    def best_ask(self):
        if not self.askPrices: return None
        price = self.askPrices[0]
        return {"ask":price, "volume":self.askVolumes[price]}

