import bisect

VOLUME_EPSILON = 1e-9

class Orderbook:
    '''
    This class holds the internal representation of a single Orderbook for a Kalshi or Polymarket asset.
    It contains a list of bid_prices and ask_prices which are stored in ascending order. It then contains dictionaries mapping a
    bidprice and askprice to their respective volume in the book.
    '''
    def __init__(self):
            """
            Initialize empty sorted price lists and price-to-volume maps for both sides of the book.
            """
            self.bid_prices =  []
            self.bid_volumes =  {}
            self.ask_prices = []
            self.ask_volumes = {}

    def _update_book(self, prices, volumes, price, volume):
        '''
        Update one side of the book at a price level, preserving ascending price order and removing empty levels.
        NOTE that volume is not a delta but instead overwrites the current volume value.
        :param prices: a bid/ask_prices list
        :param volumes: a bid/ask_volumes dictionary
        :param price: the price of the bid/ask to be updated
        :param volume: the volume of the bid/ask to replace previous volume (if it exists)
        '''

        if volume > VOLUME_EPSILON:
            if price not in volumes:
                bisect.insort(prices, price)
            volumes[price] = volume

        else: #volume is zero, negative, or floating-point dust
            if price in volumes:
                del volumes[price]
                # log n search and delete
                index = bisect.bisect_left(prices, price)
                if index < len(prices) and prices[index] == price:
                    prices.pop(index)


    def process_bid(self, price, volume):
        '''
        Update the total displayed bid volume at a price level.
        :param price: The bid price
        :param volume: The current total volume at the bid price - this overwrites the current volume value.
        '''
        self._update_book(self.bid_prices, self.bid_volumes, price, volume)


    def process_ask(self, price, volume):
        """
        Update the total displayed ask volume at a price level.
        :param price: The ask price
        :param volume: The current total volume at the ask price - this overwrites the current volume value.
        """
        self._update_book(self.ask_prices, self.ask_volumes, price, volume)

    def best_bid(self):
        """
        Returns the highest bid and its volume in the book.
        :return: A dictionary containing the highest bid and its volume in the book, with keys "price" and "volume"
        """
        if not self.bid_prices: return None
        price = self.bid_prices[-1]
        return {"price": price, "volume": self.bid_volumes[price]}

    def best_ask(self):
        """
        Returns the lowest ask and its volume in the book.
       :return: A dictionary containing the lowest ask and its volume in the book, with keys "price" and "volume"
       """
        if not self.ask_prices: return None
        price = self.ask_prices[0]
        return {"price": price, "volume": self.ask_volumes[price]}
