def get_kalshi_user_subscription_message():

    subscription_msg = {
        "id": 2,
        "cmd": "subscribe",
        "params": {
            "channels": "user_orders"
        }
    }
    return subscription_msg

