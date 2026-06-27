from py_clob_client_v2 import SignatureTypeV2

from src.polymarket_modules.polymarket_orderbook_handler import process_poly_orderbook_message, get_polymarket_subscription_message
import json
import asyncio
import logging
import websockets
from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType


from src.state_classes.events import OrderbookUpdateEvent
from src.util.enums import Exchange


async def listen_polymarket_markets(markets, orderbook_update_process_queue):
    """
    Maintain the Polymarket market WebSocket, apply book messages, and enqueue changed token IDs.
    """
    while True:
    # ... websocket connection setup ...
        try:
            uri = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
            async with websockets.connect(uri) as websocket:
                print(f"Connected to polymarket at {uri}")
                logging.info(f"Connected to polymarket at {uri}")

                message = get_polymarket_subscription_message(markets)
                await websocket.send(json.dumps(message))

                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    #print(data)
                    """
                    Book snapshots can come as a list when first subscribing to all of them, so process the lists
                    Orderbook updates come as single messages.
                    """
                    if isinstance(data, list):
                        # Lists for asset_id
                        for i in data:
                            asset_id_list = process_poly_orderbook_message(markets, i)
                            add_asset_ids_to_queue(orderbook_update_process_queue, asset_id_list)
                    else:
                        asset_id_list = process_poly_orderbook_message(markets, data)
                        add_asset_ids_to_queue(orderbook_update_process_queue, asset_id_list)


        except websockets.ConnectionClosed:
            print("[WARN] Polymarket connection lost. Reconnecting in 5s...")
            logging.error("[WARN] Polymarket connection lost. Reconnecting in 5s...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"[ERROR] Polymarket error: {e}. Reconnecting in 5s...")
            logging.error("[ERROR] Polymarket error. Reconnecting in 5s...")
            await asyncio.sleep(5)


def add_asset_ids_to_queue(orderbook_update_process_queue, asset_id_list):
    """
    Convert changed Polymarket asset IDs into orderbook update events for the strategy queue.
    """
    for asset in asset_id_list:
        if asset:
            orderbook_update_process_queue.put_nowait(OrderbookUpdateEvent(Exchange.POLYMARKET, asset))


async def get_polymarket_balance(polymarket_client):
    """
    Sync and fetch the Polymarket collateral allowance balance, returning USDC units.
    """
    collateral_params = BalanceAllowanceParams(
        asset_type=AssetType.COLLATERAL,
        signature_type=SignatureTypeV2.POLY_1271
    )

    # Force the API to sync the Deposit Wallet cache with the blockchain
    logging.info("Syncing Deposit Wallet balance with Polymarket API...")
    await asyncio.to_thread(
        polymarket_client.update_balance_allowance,
        params=collateral_params,
    )

    # Fetch the newly updated balance
    collateral_data = await asyncio.to_thread(
        polymarket_client.get_balance_allowance,
        params=collateral_params,
    )

    raw_balance = float(collateral_data.get("balance", 0))
    return raw_balance / 1_000_000
