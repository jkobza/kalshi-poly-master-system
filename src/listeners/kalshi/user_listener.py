def get_kalshi_user_subscription_message():
    """
    Build the Kalshi WebSocket subscription payload for authenticated user order updates.
    """

    subscription_msg = {
        "id": 1,
        "cmd": "subscribe",
        "params": {
            "channels": "user_orders"
        }
    }
    return subscription_msg

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
