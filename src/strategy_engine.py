import aiofiles
import logging
from src.state_classes.orderbook_update_event import OrderbookUpdateEvent
from src.util.enums import Exchange
logging.basicConfig(
    filename='../logs/bot_nightly.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
async def strategy_engine(orderbook_update_queue, order_process_queue, market_holder):


    print("Strategy engine started, waiting for market events...")
    while True:
        event = await orderbook_update_queue.get()

        exchange = event.exchange
        asset_id = event.asset_id

        if exchange == Exchange.POLYMARKET:
            kalshi_ids = market_holder.p_to_k_map.get(asset_id)
            if not kalshi_ids:
                orderbook_update_queue.task_done()
                continue

            # Get the id of the kalshi asset
            kalshi_eq_asset_id = kalshi_ids[0]

            # Get both current orderbooks


            poly_orderbook = market_holder.poly_orderbooks.get(asset_id)
            kalshi_orderbook = market_holder.kalshi_orderbooks.get(kalshi_eq_asset_id)

            if not poly_orderbook or not kalshi_orderbook:
                orderbook_update_queue.task_done()
                continue

            p_bid_data = poly_orderbook.best_bid()
            p_ask_data = poly_orderbook.best_ask()
            k_bid_data = kalshi_orderbook.best_bid()
            k_ask_data = kalshi_orderbook.best_ask()

            await process_both_orderbooks(p_bid_data, p_ask_data, k_bid_data, k_ask_data, asset_id, kalshi_eq_asset_id,order_process_queue)

        if exchange == Exchange.KALSHI:
            poly_ids = market_holder.k_to_p_map.get(asset_id)
            if not poly_ids:
                orderbook_update_queue.task_done()
                continue

            poly_eq_asset_id = poly_ids[0]
            kalshi_orderbook = market_holder.kalshi_orderbooks.get(asset_id)
            poly_orderbook = market_holder.poly_orderbooks.get(poly_eq_asset_id)

            if not poly_orderbook or not kalshi_orderbook:
                orderbook_update_queue.task_done()
                continue

                # 2. Extract the dicts
            p_bid_data = poly_orderbook.best_bid()
            p_ask_data = poly_orderbook.best_ask()
            k_bid_data = kalshi_orderbook.best_bid()
            k_ask_data = kalshi_orderbook.best_ask()

            await process_both_orderbooks(p_bid_data, p_ask_data, k_bid_data, k_ask_data, poly_eq_asset_id, asset_id,order_process_queue)

            #await log_both_orderbooks(p_bid_data, p_ask_data, k_bid_data, k_ask_data)


        orderbook_update_queue.task_done()


async def process_both_orderbooks(p_bid_data, p_ask_data, k_bid_data, k_ask_data, poly_id, kalshi_id, order_process_queue):

    if not all([p_bid_data, p_ask_data, k_bid_data, k_ask_data]):
        return

    best_poly_bid, best_poly_bid_volume = p_bid_data["bid"], p_bid_data["volume"]
    best_poly_ask, best_poly_ask_volume = p_ask_data["ask"], p_ask_data["volume"]
    best_kalshi_bid, best_kalshi_bid_volume = k_bid_data["bid"], k_bid_data["volume"]
    best_kalshi_ask, best_kalshi_ask_volume = k_ask_data["ask"], k_ask_data["volume"]

    # 2. Asynchronous File Writing
    if best_kalshi_bid - best_poly_ask > 3:
        print(f"[ARB FOUND] Kalshi Bid ({best_kalshi_bid}) > Poly Ask ({best_poly_ask})")
        logging.info(f"[ARB FOUND] Kalshi Bid ({best_kalshi_bid}) > Poly Ask ({best_poly_ask})")
        min_volume = min(best_kalshi_bid_volume, best_poly_ask_volume)
        order_process_queue.put_nowait({"bidside": "kalshi", "askside": "poly", "bid_price":best_kalshi_bid, "ask_price":best_poly_ask, "min_volume":min_volume, "kalshi_id":kalshi_id, "poly_id":poly_id })


    if best_poly_bid - best_kalshi_ask  > 3:
        print(f"[ARB FOUND] Poly Bid ({best_poly_bid}) > Kalshi Ask ({best_kalshi_ask})")
        logging.info(f"[ARB FOUND] Poly Bid ({best_poly_bid}) > Kalshi Ask ({best_kalshi_ask})")
        min_volume = min(best_poly_bid_volume, best_kalshi_ask_volume)
        order_process_queue.put_nowait({"bidside": "poly", "askside": "kalshi", "bid_price":best_poly_bid, "ask_price":best_kalshi_ask, "min_volume":min_volume, "kalshi_id":kalshi_id, "poly_id":poly_id })



#
#
# async def log_both_orderbooks(p_bid_data, p_ask_data, k_bid_data, k_ask_data):
#     # 1. Guard against None (empty books)
#     if not all([p_bid_data, p_ask_data, k_bid_data, k_ask_data]):
#         return
#
#     best_poly_bid, best_poly_bid_volume = p_bid_data["bid"], p_bid_data["volume"]
#     best_poly_ask, best_poly_ask_volume = p_ask_data["ask"], p_ask_data["volume"]
#     best_kalshi_bid, best_kalshi_bid_volume = k_bid_data["bid"], k_bid_data["volume"]
#     best_kalshi_ask, best_kalshi_ask_volume = k_ask_data["ask"], k_ask_data["volume"]
#
#     # 2. Asynchronous File Writing
#     if best_kalshi_bid > best_poly_ask + (0.07 * best_kalshi_bid * (1 - best_kalshi_bid)):
#         async with aiofiles.open('../../results.csv', mode='a', newline='') as csvfile:
#             row = f"Arb opportunity: Kalshi bid:,{best_kalshi_bid},Poly ask:,{best_poly_ask},Min volume:,{min(best_kalshi_bid_volume, best_poly_ask_volume)}\n"
#             await csvfile.write(row)
#
#         print(f"[ARB FOUND] Kalshi Bid ({best_kalshi_bid}) > Poly Ask ({best_poly_ask})")
#         logging.info(f"[ARB FOUND] Kalshi Bid ({best_kalshi_bid}) > Poly Ask ({best_poly_ask})")
#
#
#     if best_poly_bid > best_kalshi_ask + (0.07 * best_kalshi_ask * (1 - best_kalshi_ask)):
#         async with aiofiles.open('../../results.csv', mode='a', newline='') as csvfile:
#             row = f"Arb opportunity: Poly bid:,{best_poly_bid},Kalshi ask:,{best_kalshi_ask},Min volume:,{min(best_kalshi_ask_volume, best_poly_bid_volume)}\n"
#             await csvfile.write(row)
#
#         print(f"[ARB FOUND] Poly Bid ({best_poly_bid}) > Kalshi Ask ({best_kalshi_ask})")
#         logging.info(f"[ARB FOUND] Poly Bid ({best_poly_bid}) > Kalshi Ask ({best_kalshi_ask})")