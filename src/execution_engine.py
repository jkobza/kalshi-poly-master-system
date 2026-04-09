import asyncio
async def execution_engine(order_process_queue, market_holder, position_manager):
    print("Strategy engine started, waiting for market events...")
    while True:
        event = await order_process_queue.get()

        bidside = event["bidside"]
        askside = event["askside"]
        bid_price = event["bid_price"]
        ask_price = event["ask_price"]
        min_volume = event["min_volume"]
        if(bidside == "kalshi"):
            bid_id = event["kalshi_id"] # kalshi bid is higher than poly ask, so buy on poly, sell on kalshi
            ask_id = event["poly_id"]

            await asyncio.gather(
                position_manager.post_poly_order(ask_id, "BUY", ask_price, 10),
                position_manager.post_kalshi_order(bid_id, "SELL", bid_price, 10)
            )

        elif(bidside == "poly"):
            bid_id = event["poly_id"] # poly bid is higher than kalshi ask, so buy on kalshi, sell on poly
            ask_id = event["kalshi_id"]
            await asyncio.gather(
                position_manager.post_kalshi_order(ask_id, "BUY", ask_price, 10),
                position_manager.post_poly_order(bid_id, "SELL", bid_price, 10)
            )

        print("Entering 5-minute cooldown...")
        await asyncio.sleep(300)
        cleared_count = 0
        while not order_process_queue.empty():
            try:
                order_process_queue.get_nowait()
                order_process_queue.task_done()
                cleared_count += 1
            except asyncio.QueueEmpty:
                break

        if cleared_count > 0:
            print(f"Cleared {cleared_count} stale signals from the queue.")

        print("Cooldown finished. Resuming execution...")










