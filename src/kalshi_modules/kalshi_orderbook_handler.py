from src.state_classes.market_holder import MarketHolder
from src.state_classes.orderbook import Orderbook


def get_kalshi_market_subscription_message(markets: MarketHolder):
    '''
    Create the Kalshi WebSocket subscription message for every tracked market ticker.
    :param markets: The singleton marketHolder instance
    :return: A JSON-serializable subscription payload for the orderbook_delta channel.

    '''
    asset_ids = []
    for i in markets.kalshi_orderbooks.keys():
        asset_ids.append(str(i))
    #print(assetIds)
    subscription_msg = {
        "id": 2,
        "cmd": "subscribe",
        "params": {
            "channels": ["orderbook_delta"],
            "market_tickers": asset_ids
        }
    }
    return subscription_msg


def process_kalshi_orderbook_message(markets, message):
    '''
    Process a Kalshi orderbook snapshot or delta and return the affected market ticker.
    :param markets: The singleton marketHolder instance
    :param message: The message to process
    :return: A one-item asset ID list when a tracked book changed, otherwise None.

    Note: Kalshi omits yes_dollars_fp / no_dollars_fp when that side has no resting offers
    (common for settled or empty books).
    '''
    msg_type = message.get("type")
    if msg_type == "orderbook_snapshot":
        new_book = Orderbook()
        book_update = message["msg"]
        asset_id = book_update["market_ticker"]

        # Keys are optional when a side has no liquidity.
        for yes_bid in book_update.get("yes_dollars_fp") or []:
            new_book.process_bid(float(yes_bid[0]), float(yes_bid[1]))
        for no_bid in book_update.get("no_dollars_fp") or []:
            ask_price = round(1.0 - float(no_bid[0]), 4)
            new_book.process_ask(ask_price, float(no_bid[1]))

        markets.kalshi_orderbooks[asset_id] = new_book
        #print(f"[KALSHI BOOK SNAPSHOT]: Ticker = {asset_id} Best Bid: " + str(new_book.best_bid()) + " Best Ask: " + str(new_book.best_ask()))
        return [asset_id]


    elif msg_type == "orderbook_delta":
        book_update = message["msg"]
        asset_id = book_update["market_ticker"]
        if asset_id in markets.kalshi_orderbooks:
            book = markets.kalshi_orderbooks[asset_id]

            prev_best_bid = book.best_bid()
            prev_best_ask = book.best_ask()

            price = float(book_update['price_dollars'])

            # delta_fp is the relative CHANGE in volume
            delta = float(book_update['delta_fp'])
            side = book_update["side"]
            if side == "yes":
                current_vol = book.bid_volumes.get(price, 0.0)
                book.process_bid(price, current_vol + delta)
            elif side == "no":
                ask_price = round(1.0 - price, 4)
                current_vol = book.ask_volumes.get(ask_price, 0.0)
                book.process_ask(ask_price, current_vol + delta)

            return [asset_id]

    return None
