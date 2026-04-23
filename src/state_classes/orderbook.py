import bisect

class Orderbook:
    '''
    This class holds the internal representation of a single Orderbook for a Kalshi or Polymarket asset.
    It contains a list of bidPrices and askPrices which are stored in ascending order. It then contains dictionaries mapping a
    bidprice and askprice to their respective volume in the book.
    '''
    def __init__(self):
            self.bidPrices =  []
            self.bidVolumes =  {}
            self.askPrices = []
            self.askVolumes = {}

    def _update_book(self, prices, volumes, price, volume):
        '''
        This helper method takes in a bid/askPrices list and a bid/askVolumes dictionary and updates the order book
        at that price and volume. It will put prices in ascending order in the list.
        NOTE that volume is not a delta but instead overwrites the current volume value.
        :param prices: a bid/askPrices list
        :param volumes: a bid/askVolumes dictionary
        :param price: the price of the bid/ask to be updated
        :param volume: the volume of the bid/ask to replace previous volume (if it exists)
        '''
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


    def process_bid(self, price, volume):
        '''
        This helper method takes in a bid price and volume and calls the _update_book function with the bidPrices list
        and bidVolumes dictionary.
        :param price: The bid price
        :param volume: The current total volume at the bid price - this overwrites the current volume value.
        :return:
        '''
        self._update_book(self.bidPrices, self.bidVolumes, price, volume)


    def process_ask(self, price, volume):
        """
        This helper method takes in a ask price and volume and calls the _update_book function with the askPrices list
        and askVolumes dictionary.
        :param price: The ask price
        :param volume: The current total volume at the ask price - this overwrites the current volume value.
        :return:
        """
        self._update_book(self.askPrices, self.askVolumes, price, volume)

    def best_bid(self):
        """
        Returns the highest bid and its volume in the book.
        :return: A dictionary containing the highest bid and its volume in the book, with keys "price" and "volume"
        """
        if not self.bidPrices: return None
        price = self.bidPrices[-1]
        return {"price": price, "volume": self.bidVolumes[price]}

    def best_ask(self):
        """
       Returns the highest bid and its volume in the book.
       :return: A dictionary containing the highest bid and its volume in the book, with keys "price" and "volume"
       """
        if not self.askPrices: return None
        price = self.askPrices[0]
        return {"price": price, "volume": self.askVolumes[price]}

