from src.polymarket_modules.polymarket_orderbook_handler import process_poly_orderbook_message, get_poly_market_subscription_message
import json
import asyncio
import logging
import websockets

async def listen_polymarket_markets(markets, signal_process_queue):
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
                            asset_id = process_poly_orderbook_message(markets, i)
                            if asset_id:
                                signal_process_queue.put_nowait({"exchange": "polymarket", "asset_id": asset_id})
                    else:
                        asset_id = process_poly_orderbook_message(markets, data)
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