import asyncio
import uuid

from src.state_classes.market_holder import MarketHolder
from src.state_classes.position_manager import PositionManager
from py_clob_client.clob_types import OrderArgs, PartialCreateOrderOptions
from kalshi_python_async.models import CreateOrderRequest

class ExecutionEngine:

    def __init__(self, order_process_queue: asyncio.Queue, market_holder:MarketHolder, position_manager: PositionManager, poly_client, kalshi_client):
        self.order_process_queue = order_process_queue
        self.market_holder = market_holder
        self.position_manager = position_manager
        self.poly_client = poly_client
        self.kalshi_client = kalshi_client


    async def execution_engine(self):
        print("Strategy engine started, waiting for market events...")
        while True:
            event = await self.order_process_queue.get()

            bidside = event["bidside"]
            askside = event["askside"]
            bid_price = event["bid_price"]
            ask_price = event["ask_price"]
            min_volume = event["min_volume"]
            if(bidside == "kalshi"):
                bid_id = event["kalshi_id"] # kalshi bid is higher than poly ask, so buy on poly, sell on kalshi
                ask_id = event["poly_id"]

                await asyncio.gather(
                    self.post_poly_order(ask_id, "BUY", ask_price, 10),
                    self.post_kalshi_order(bid_id, "SELL", bid_price, 10)
                )

            elif(bidside == "poly"):
                bid_id = event["poly_id"] # poly bid is higher than kalshi ask, so buy on kalshi, sell on poly
                ask_id = event["kalshi_id"]

                # TODO - Order ACKs
                kalshi_order, poly_order = await asyncio.gather(
                    self.post_kalshi_order(ask_id, "BUY", ask_price, 10),
                    self.post_poly_order(bid_id, "SELL", bid_price, 10),
                return_exceptions = True
                )

            print("Entering 5-minute cooldown...")
            await asyncio.sleep(300)
            cleared_count = 0
            while not self.order_process_queue.empty():
                try:
                    self.order_process_queue.get_nowait()
                    self.order_process_queue.task_done()
                    cleared_count += 1
                except asyncio.QueueEmpty:
                    break

            if cleared_count > 0:
                print(f"Cleared {cleared_count} stale signals from the queue.")

            print("Cooldown finished. Resuming execution...")

    async def post_kalshi_order(self, ticker: str, action: str, price: float, volume: int):
        order_request = CreateOrderRequest(
            ticker=ticker,
            action=action.lower(),
            side="yes",
            count=volume,
            yes_price_dollars=price,
            client_order_id=str(uuid.uuid4())
        )

        try:
            response = await self.kalshi_client.create_order(order_request)

            order_id = response.order.order_id
            status = response.order.status.lower()

            print(f"Kalshi Order Placed! ID: {order_id} | Status: {status}")

            # TODO - add orders to position manager and return

        except Exception as e:
            print(f"Failed to place Kalshi order: {e}")
            return None

    async def post_poly_order(self, token_id, side, price, volume):
        tick_size = await asyncio.to_thread(self.poly_client.get_tick_size, token_id)

        order_args = OrderArgs(
            token_id=token_id,
            price=price,
            size=volume,
            side=side
        )
        options = PartialCreateOrderOptions(
            tick_size=tick_size,
            neg_risk=False
        )
        response = await asyncio.to_thread(
            self.poly_client.create_and_post_order,
            order_args,
            options=options
        )

        order_id = response.get("orderID")
        status = response.get("status", "resting").lower()
        print(f"Poly Order Placed! ID: {order_id} | Status: {status}")

        # TODO - add orders to position manager and return










