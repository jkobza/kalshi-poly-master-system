import json
import websockets
import asyncio
from src.kalshi_modules.generate_kalshi_credentials import get_kalshi_headers

# WebSocket URL
ws_url = "wss://api.elections.kalshi.com/trade-api/ws/v2"

# Generate authentication headers (see API Keys documentation)
auth_headers = get_kalshi_headers(ws_url)
"""
This file has simple manual tests for Kalshi WebSocket subscriptions.
"""

async def subscribe_to_orderbook(websocket, market_tickers):
    """
    Send a Kalshi orderbook_delta subscription for the supplied market tickers.
    """
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
    """
    Open an authenticated Kalshi WebSocket, subscribe to sample tickers, and print each message.
    """
    async with websockets.connect(ws_url, additional_headers=auth_headers) as websocket:
        print("Connected to Kalshi WebSocket")
        await subscribe_to_orderbook(websocket, ["KXNCAAMBGAME-26APR04MICHARIZ-MICH", "KXNCAAMBGAME-26APR04MICHARIZ-ARIZ"])
        async for message in websocket:
            print(f"Received: {message}")

    return websocket


# Run the connection
asyncio.run(connect())
