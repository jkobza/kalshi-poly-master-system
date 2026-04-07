'''
General idea:
Create one marketholder instance: Singleton
Put all poly and kalshi market Ids that I find into 2 lists, and have websockets monitor them,
updating the order books as it goes.
When a price is updated, check opposing market, do spread math, and execute trade at min size between sides
Currently, do not have any logic for redeeming/selling before event closes. Just sit and wait and figure out after
'''
import asyncio
import json
import websockets
import aiohttp
from marketholder import MarketHolder
from orderbook import Orderbook
from util.generateKalshiCredentials import get_kalshi_headers
from polymarkethandler import process_poly_message, get_poly_market_subscription_message
from kalshihandler import process_kalshi_message, get_kalshi_market_subscription_message
markets = MarketHolder()

#Fire up websocket streams


async def listen_polymarket():

    # ... websocket connection setup ...
    try:
        uri = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        async with websockets.connect(uri) as websocket:
            print(f"Connected to polymarket at {uri}")

            message = get_poly_market_subscription_message(markets)
            await websocket.send(json.dumps(message))

            while True:
                message = await websocket.recv()
                data = json.loads(message)
                #print(data)
                # book updates can come as a list or regular dict
                if isinstance(data, list):
                    for i in data:
                        process_poly_message(markets, i)
                else:
                    process_poly_message(markets, data)

    except ConnectionRefusedError:
        print(f"Could not connect to server. Is the server running at {uri}?")
    except Exception as e:
        print(f"An error occurred: {e}")

async def listen_kalshi():

    try:
        uri = "wss://api.elections.kalshi.com/trade-api/ws/v2"
        auth_headers = get_kalshi_headers(uri)
        async with websockets.connect(uri, additional_headers=auth_headers) as websocket:
            print("Connected to Kalshi WebSocket")
            message = get_kalshi_market_subscription_message(markets)
            print(message)
            await websocket.send(json.dumps(message))

            while True:
                message = await websocket.recv()
                data = json.loads(message)
                #print(data)
                process_kalshi_message(markets, data)

    except ConnectionRefusedError:
        print(f"Could not connect to server. Is the server running at {uri}?")
    except Exception as e:
        print(f"An error occurred: {e}")





async def main():
    print("Starting market listeners...")
    # asyncio.gather runs both coroutines concurrently
    await asyncio.gather(
        listen_polymarket(),
        listen_kalshi()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down engine...")