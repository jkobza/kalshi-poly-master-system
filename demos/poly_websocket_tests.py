import websockets
import asyncio
import json


async def connect_to_polymarket_websocket():
    """
    Connect to the Polymarket market WebSocket with sample token IDs and print incoming messages.
    """
    try:
        uri = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        async with websockets.connect(uri) as websocket:
            print(f"Connected to polymarket at {uri}")

            testMessage =  {
                    "assets_ids": [
                        "13651748497091237808460113623486770193427477134717425380391907960466586656575"
                        ,"30749752882380468581455841009460065689112582074809192530663606496981501013213"
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
