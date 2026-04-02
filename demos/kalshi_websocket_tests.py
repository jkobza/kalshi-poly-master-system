import json
import websockets
import asyncio
from util.generateKalshiCredentials import get_kalshi_headers
from util.generateKalshiCredentials import send_auth_kalshi_message
# WebSocket URL
ws_url = "wss://api.elections.kalshi.com/trade-api/ws/v2"

# Generate authentication headers (see API Keys documentation)
auth_headers = get_kalshi_headers(ws_url)


async def subscribe_to_orderbook(websocket, market_tickers):
    """Subscribe to orderbook updates for specific markets"""
    subscription = {
        "id": 2,
        "cmd": "subscribe",
        "params": {
            "channels": ["orderbook_delta"],
            "market_tickers": market_tickers
        }
    }
    await websocket.send(json.dumps(subscription))

# Connect with authentication
async def connect():
    async with websockets.connect(ws_url, additional_headers=auth_headers) as websocket:
        print("Connected to Kalshi WebSocket")
        await subscribe_to_orderbook(websocket, ["KXNCAAMBGAME-26APR04MICHARIZ-MICH", "KXNCAAMBGAME-26APR04MICHARIZ-ARIZ"])
        async for message in websocket:
            print(f"Received: {message}")

    return websocket


# Run the connection
asyncio.run(connect())