import uuid

from src.classes.market_holder import MarketHolder
from dataclasses import dataclass
import asyncio
from py_clob_client.clob_types import OrderArgs, PartialCreateOrderOptions
from kalshi_python_async.models import CreateOrderRequest

@dataclass
class Order:
    id: str
    exchange: str
    status: str
    asset_id: str
    side: str
    price: float
    original_size: float
    size_matched: float

@dataclass
class Position:
    kalshi_id: str
    poly_id: str
    kalshi_side: str
    poly_side: str
    kalshi_price: float
    poly_price: float
    size: float
    spread_including_fees: float




class PositionManager:



    def __init__(self, market_holder:MarketHolder, poly_client, kalshi_client):
        self.kalshi_open_orders = {}
        self.polymarket_open_orders = {}
        self.kalshi_client = kalshi_client
        self.poly_client = poly_client
        self.positions = {}
        self.in_flight_arbs = {}
        self.market = market_holder

    async def updateOpenOrders(self):
        self.polymarket_open_orders = {}
        self.kalshi_open_orders = {}

        # Fetch from both exchanges concurrently so you don't waste time waiting twice
        poly_task = asyncio.to_thread(self.poly_client.get_orders)
        kalshi_task = self.kalshi_client.get_orders(status="resting")  # Only grab open orders

        poly_orders, kalshi_response = await asyncio.gather(poly_task, kalshi_task)

        for order in poly_orders:
            norm_order = Order(
                id=order.id,
                exchange="polymarket",
                status=order.status.lower(),  # Normalize casing
                asset_id=order.asset_id,
                side=order.side.lower(),
                price=float(order.price),
                original_size=float(order.original_size),
                size_matched=float(order.size_matched)
            )
            self.polymarket_open_orders[norm_order.id] = norm_order

        # --- Process Kalshi Orders ---
        # Note: kalshi_response.orders contains the list
        for order in kalshi_response.orders:

            size_matched = order.count - (order.remaining_count if hasattr(order, 'remaining_count') else 0)

            norm_order = Order(
                id=order.order_id,
                exchange="kalshi",
                status=order.status.lower(),
                asset_id=order.ticker,
                side=order.action.lower(),  # "buy" or "sell"
                price=order.yes_price_dollars,  # Convert cents back to float dollars!
                original_size=float(order.count),
                size_matched=float(size_matched)
            )
            self.kalshi_open_orders[norm_order.id] = norm_order

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

        # FIXED: Use the new Order class, add exchange, format as floats
        new_order = Order(
            id=order_id,
            exchange="polymarket",
            status=status,
            asset_id=token_id,
            side=side.lower(),
            price=float(price),
            original_size=float(volume),
            size_matched=0.0
        )

        self.polymarket_open_orders[order_id] = new_order
        return new_order

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

            new_order = Order(
                id=order_id,
                exchange="kalshi",
                status=status,
                asset_id=ticker,
                side=action.lower(),
                price=float(price),
                original_size=float(volume),
                size_matched=0.0
            )

            self.kalshi_open_orders[order_id] = new_order
            return new_order

        except Exception as e:
            print(f"Failed to place Kalshi order: {e}")
            return None





