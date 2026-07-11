from src.kalshi_modules.kalshi_orderbook_handler import process_kalshi_orderbook_message, get_kalshi_market_subscription_message
from src.kalshi_modules.kalshi_user_handler import get_kalshi_user_subscription_message
import websockets
import logging
from src.kalshi_modules.generate_kalshi_credentials import get_kalshi_headers
import json
import asyncio
from src.state_classes.events import OrderbookUpdateEvent
from src.util.enums import Exchange


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
            logging.exception("Kalshi listener error. Reconnecting in 5s...")
            await asyncio.sleep(5)
'''
async def listen_kalshi_user(position_manager: PositionManager, signal_process_queue):
    # TODO
    while True:
        try:
            uri = "wss://api.elections.kalshi.com/trade-api/ws/v2"
            auth_headers = get_kalshi_headers(uri)
            async with websockets.connect(uri, additional_headers=auth_headers) as websocket:
                print("Connected to Kalshi WebSocket")
                logging.info(f"Connected to Kalshi WebSocket")
                message = get_kalshi_user_subscription_message()
                await websocket.send(json.dumps(message))

                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    update = process_kalshi_user_message(markets, data)
                    if update:
                        signal_process_queue.put_nowait(update)

        except websockets.ConnectionClosed:
            print("[WARN] Kalshi connection lost. Reconnecting in 5s...")
            logging.error("[WARN] Kalshi connection lost. Reconnecting in 5s...")
            await asyncio.sleep(5)

        except Exception as e:
            print(f"[ERROR] Kalshi error: {e}. Reconnecting in 5s...")
            logging.error("[ERROR] Kalshi error. Reconnecting in 5s...")
            await asyncio.sleep(5)
'''
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
