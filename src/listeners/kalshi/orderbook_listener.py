import websockets
import logging
from src.kalshi_modules.generate_kalshi_credentials import get_kalshi_headers
import json
import asyncio
from src.state_classes.arb_holder import ArbHolder
from src.state_classes.orderbook import Orderbook
from src.state_classes.events import OrderbookUpdateEvent, Exchange


def get_kalshi_market_subscription_message(markets: ArbHolder):
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
        return [asset_id]


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
                current_vol = book.bid_volumes.get(price, 0.0)
                book.process_bid(price, current_vol + delta)
            elif side == "no":
                ask_price = round(1.0 - price, 4)
                current_vol = book.ask_volumes.get(ask_price, 0.0)
                book.process_ask(ask_price, current_vol + delta)

            return [asset_id]


async def listen_kalshi_markets(markets, orderbook_update_process_queue):
    """
    Maintain the Kalshi market WebSocket, apply orderbook messages, and enqueue changed market tickers.
    """
    while True:
        try:
            uri = "wss://api.elections.kalshi.com/trade-api/ws/v2"
            auth_headers = get_kalshi_headers(uri)
            async with websockets.connect(uri, additional_headers=auth_headers) as websocket:
                print("Connected to Kalshi WebSocket")
                logging.info(f"Connected to Kalshi WebSocket")
                message = get_kalshi_market_subscription_message(markets)
                await websocket.send(json.dumps(message))

                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    asset_id = process_kalshi_orderbook_message(markets, data)
                    if asset_id:
                        add_asset_ids_to_queue(orderbook_update_process_queue, asset_id)

        except websockets.ConnectionClosed:
            print("[WARN] Kalshi connection lost. Reconnecting in 5s...")
            logging.error("[WARN] Kalshi connection lost. Reconnecting in 5s...")
            await asyncio.sleep(5)

        except Exception as e:
            print(f"[ERROR] Kalshi error: {e}. Reconnecting in 5s...")
            logging.error("[ERROR] Kalshi error. Reconnecting in 5s...")
            await asyncio.sleep(5)
def add_asset_ids_to_queue(orderbook_update_process_queue, asset_id_list):
    """
    Convert changed Kalshi asset IDs into orderbook update events for the strategy queue.
    """
    for asset in asset_id_list:
        if asset:
            orderbook_update_process_queue.put_nowait(OrderbookUpdateEvent(Exchange.KALSHI, asset))

async def get_kalshi_balance(kalshi_client):
    """
    Fetch the Kalshi portfolio balance and convert cents to dollars.
    """
    response = await kalshi_client.get_balance()
    return float(response.balance) / 100
