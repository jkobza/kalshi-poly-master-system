from src.kalshi_modules.generate_kalshi_credentials import get_kalshi_headers
from src.state_classes.market_holder import MarketHolder
from src.state_classes.orderbook import Orderbook

# WebSocket URL
ws_url = "wss://api.elections.kalshi.com/trade-api/ws/v2"

# Generate authentication headers (see API Keys documentation)
auth_headers = get_kalshi_headers(ws_url)


def get_kalshi_market_subscription_message(markets: MarketHolder):
    '''
    Creates the kalshi websocket subscription message to subscribe to all Kalshi markets
    held in the marketHolder instance
    :param markets: The singleton marketHolder instance

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
    Processes a kalshi websocket orderbook message and returns the corresponding assetId
    There are two types of messages, orderbook snapshots and orderbook updates. Each are handled seperately
    :param markets: The singleton marketHolder instance
    :param message: The message to process
    '''
    if message["type"] == "orderbook_snapshot":
        new_book = Orderbook()
        book_update = message["msg"]
        asset_id = book_update["market_ticker"]

        for yes_bid in book_update["yes_dollars_fp"]:
            new_book.process_bid(float(yes_bid[0]), float(yes_bid[1]))
        for no_bid in book_update["no_dollars_fp"]:
            ask_price = round(1.0 - float(no_bid[0]), 4)
            new_book.process_ask(ask_price, float(no_bid[1]))

        markets.kalshi_orderbooks[asset_id] = new_book
        #print(f"[KALSHI BOOK SNAPSHOT]: Ticker = {asset_id} Best Bid: " + str(new_book.best_bid()) + " Best Ask: " + str(new_book.best_ask()))
        return asset_id


    elif message['type'] == "orderbook_delta":
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
                current_vol = book.bidVolumes.get(price, 0.0)
                book.process_bid(price, current_vol + delta)
            elif side == "no":
                ask_price = round(1.0 - price, 4)
                current_vol = book.askVolumes.get(ask_price, 0.0)
                book.process_ask(ask_price, current_vol + delta)

            return asset_id
