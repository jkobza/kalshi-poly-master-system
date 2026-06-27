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
