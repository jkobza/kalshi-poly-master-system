'''
General idea:
Create one marketholder instance: Singleton
Put all poly and kalshi market Ids that I find into 2 lists, and have websockets monitor them,
updating the order books as it goes.
When a price is updated, check opposing market, do spread math, and execute trade at min size between sides
Currently, do not have any logic for redeeming/selling before event closes. Just sit and wait and figure out after
'''
import asyncio
import json
import websockets
import aiohttp
import logging
from market_holder import MarketHolder
from orderbook import Orderbook
from position_manager import PositionManager
from strategy_engine import strategy_engine
from execution_engine import execution_engine
from util.generate_kalshi_credentials import get_kalshi_headers, get_kalshi_client
from util.generate_poly_credentials import get_poly_client
from polymarket_handler import process_poly_message, get_poly_market_subscription_message
from kalshi_handler import process_kalshi_message, get_kalshi_market_subscription_message

logging.basicConfig(
    filename='bot_nightly.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

#Fire up websocket streams


async def listen_polymarket(markets, signal_process_queue):
    while True:
    # ... websocket connection setup ...
        try:
            uri = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
            async with websockets.connect(uri) as websocket:
                print(f"Connected to polymarket at {uri}")
                logging.info(f"Connected to polymarket at {uri}")

                message = get_poly_market_subscription_message(markets)
                await websocket.send(json.dumps(message))

                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    #print(data)
                    # book updates can come as a list or regular dict
                    if isinstance(data, list):
                        for i in data:
                            asset_id = process_poly_message(markets, i)
                            if asset_id:
                                signal_process_queue.put_nowait({"exchange": "polymarket", "asset_id": asset_id})
                    else:
                        asset_id = process_poly_message(markets, data)
                        if asset_id:
                            signal_process_queue.put_nowait({"exchange": "polymarket", "asset_id": asset_id})


        except websockets.ConnectionClosed:
            print("[WARN] Polymarket connection lost. Reconnecting in 5s...")
            logging.error("[WARN] Polymarket connection lost. Reconnecting in 5s...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"[ERROR] Polymarket error: {e}. Reconnecting in 5s...")
            logging.error("[ERROR] Polymarket error. Reconnecting in 5s...")
            await asyncio.sleep(5)

async def listen_kalshi(markets, signal_process_queue):
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
                    asset_id = process_kalshi_message(markets, data)
                    if asset_id:
                        signal_process_queue.put_nowait({"exchange": "kalshi", "asset_id": asset_id})

        except websockets.ConnectionClosed:
            print("[WARN] Kalshi connection lost. Reconnecting in 5s...")
            logging.error("[WARN] Kalshi connection lost. Reconnecting in 5s...")
            await asyncio.sleep(5)

        except Exception as e:
            print(f"[ERROR] Kalshi error: {e}. Reconnecting in 5s...")
            logging.error("[ERROR] Kalshi error. Reconnecting in 5s...")
            await asyncio.sleep(5)


async def main():
        print("Starting engine...")
        logging.info("Starting engine...")

        markets = MarketHolder()
        poly_client = get_poly_client()
        kalshi_client = get_kalshi_client()
        positions = PositionManager(markets, poly_client, kalshi_client)

        signal_process_queue = asyncio.Queue()
        order_process_queue = asyncio.Queue()

        await asyncio.gather(
            listen_polymarket(markets,signal_process_queue),
            listen_kalshi(markets, signal_process_queue),
            strategy_engine(signal_process_queue, order_process_queue, markets),
            execution_engine(order_process_queue, markets, positions)
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down engine...")
        logging.info("Shutting down engine...")