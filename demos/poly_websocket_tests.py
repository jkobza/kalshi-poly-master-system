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
                        "20996999543007691583276658905733278225425842004273126945333981068139574656671",
                        "44766497521417298224542775684305151578865412839932497569295014747238754685930"
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