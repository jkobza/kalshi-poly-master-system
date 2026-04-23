def get_kalshi_user_subscription_message():

    subscription_msg = {
        "id": 1,
        "cmd": "subscribe",
        "params": {
            "channels": "user_orders"
        }
    }
    return subscription_msg

