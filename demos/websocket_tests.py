import websockets
import asyncio
import json

async def connect_to_polymarket_websocket():
    try:
        uri = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        async with websockets.connect(uri) as websocket:
            print(f"Connected to polymarket at {uri}")

            testMessage =  {
                    "assets_ids": [
                        "84007361241758978489330197202827235700289078898880514910472901778979242019662",
                        "62722671790005482936206654382262146252373495629515527865660421386850609062191"
                    ],
                    "type": "market",
                    "custom_feature_enabled": False
                }

            await websocket.send(json.dumps(testMessage))
            print(f"> Sent: {testMessage}")

            while True:
                message = await websocket.recv()
                print(f"Received: {message}")

    except ConnectionRefusedError:
        print(f"Could not connect to server. Is the server running at {uri}?")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(connect_to_polymarket_websocket())