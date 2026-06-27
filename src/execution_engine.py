import asyncio
import csv
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import requests
import uuid

from src.kalshi_modules.generate_kalshi_credentials import get_kalshi_headers
from src.state_classes.events import ExecutionEvent
from src.state_classes.market_holder import MarketHolder
from src.state_classes.order import Order
from src.state_classes.position_manager import PositionManager
from py_clob_client_v2.clob_types import MarketOrderArgs, PartialCreateOrderOptions, OrderType
from py_clob_client_v2.order_builder.constants import BUY,SELL
from src.state_classes.position import Position


from src.util.enums import OrderStatus, Exchange, OrderSide, PositionStatus


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRADE_LOG_PATH = PROJECT_ROOT / "logs" / "trades.csv"
TRADE_LOG_FIELDS = [
    "timestamp_utc",
    "exchange",
    "asset_id",
    "side",
    "price",
    "size",
    "status",
    "external_order_id",
    "api_status",
    "defer_exec",
    "error",
]


def enum_name(value):
    """
    Return an enum member name when available, otherwise fall back to a string representation.
    """
    return value.name if hasattr(value, "name") else str(value)


class ExecutionEngine:

    def __init__(self, execution_queue: asyncio.Queue, market_holder:MarketHolder, position_manager: PositionManager, poly_client, kalshi_client):
        """
        Keep the execution queue, shared market state, position manager, and authenticated exchange clients.
        """
        self.execution_queue = execution_queue
        self.market_holder = market_holder
        self.position_manager = position_manager
        self.poly_client = poly_client
        self.kalshi_client = kalshi_client

    def append_trade_csv(self, row):
        """
        Append one normalized trade-attempt row to the CSV log, creating the file and header when needed.
        """
        try:
            TRADE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            file_exists = TRADE_LOG_PATH.exists()
            with TRADE_LOG_PATH.open("a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=TRADE_LOG_FIELDS)
                if not file_exists:
                    writer.writeheader()
                writer.writerow({field: row.get(field, "") for field in TRADE_LOG_FIELDS})
        except Exception:
            logging.exception("Failed to append trade CSV")


    async def post_kalshi_order(self, token_id: str, side: OrderSide, price: float, volume: int):
        """
        Submit a Kalshi yes-side fill-or-kill order, update cash on fills, log the attempt, and return an Order.
        """
        if side == OrderSide.BUY:
            action = "buy"
        else: action = "sell"

        url = "https://api.elections.kalshi.com/trade-api/v2/portfolio/orders"
        payload = {
            "ticker": token_id,
            "action": action,
            "side": "yes",
            "count": volume,
            "yes_price_dollars": f"{price:.4f}",
            "time_in_force": "fill_or_kill",
            "client_order_id": str(uuid.uuid4()),
        }

        try:
            headers = get_kalshi_headers(url, method="POST")
            headers["Content-Type"] = "application/json"
            response = await asyncio.to_thread(
                requests.post,
                url,
                json=payload,
                headers=headers,
                timeout=10,
            )

            if response.status_code >= 400:
                logging.info(f"Failed to place Kalshi order: {response.status_code} {response.text}")
                self.append_trade_csv({
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "exchange": "KALSHI",
                    "asset_id": token_id,
                    "side": enum_name(side),
                    "price": price,
                    "size": volume,
                    "status": "REJECTED",
                    "api_status": response.status_code,
                    "error": response.text,
                })
                return None

            response_data = response.json()
            order_data = response_data.get("order", {})

            order_id = order_data.get("order_id")
            fill_count = order_data.get("fill_count") or order_data.get("fill_count_fp") or 0
            is_filled = float(fill_count) > 0
            order_status = OrderStatus.FILLED if is_filled else OrderStatus.KILLED

            if order_status == OrderStatus.FILLED:
                self.position_manager.kalshi_balance += self.balance_delta(price, volume, side, Exchange.KALSHI)

            result = Order(external_order_id=order_id,status=order_status, exchange=Exchange.KALSHI,
                           side=side,price=price, size=volume, asset_id=token_id)
            logging.info(f"Kalshi Order Placed! ID: {order_id}, asset_id: {token_id}, price {price}, size{volume} | Status: {order_status}")
            self.append_trade_csv({
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "exchange": "KALSHI",
                "asset_id": token_id,
                "side": enum_name(side),
                "price": price,
                "size": volume,
                "status": enum_name(order_status),
                "external_order_id": order_id,
            })
            return result

        except Exception as e:
            logging.info(f"Failed to place Kalshi order: {e}")
            self.append_trade_csv({
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "exchange": "KALSHI",
                "asset_id": token_id,
                "side": enum_name(side),
                "price": price,
                "size": volume,
                "status": "ERROR",
                "error": str(e),
            })
            return None

    async def post_poly_order(self, token_id, side, price, volume):
        """
        Submit a Polymarket fill-or-kill market order, update cash on matched fills, log the attempt, and return an Order.
        """
        try:
            tick_size = await asyncio.to_thread(self.poly_client.get_tick_size, token_id)

            if side == OrderSide.BUY:
                action = BUY
            else: action = SELL

            if side == OrderSide.BUY:
                amount = price * volume
            else:
                amount = volume

            order_args = MarketOrderArgs(
                token_id=token_id,
                amount=amount,
                price=price,
                side=action,
                order_type=OrderType.FOK,
                user_usdc_balance=self.position_manager.poly_balance,
            )
            options = PartialCreateOrderOptions(
                tick_size=tick_size,
                neg_risk=False
            )
            defer_exec = os.getenv("POLY_DEFER_EXEC", "").lower() in {"1", "true", "yes"}
            logging.info(
                f"Posting Polymarket market order | "
                f"side={action} | amount={amount} | price={price} | size={volume}"
            )
            response = await asyncio.to_thread(
                self.poly_client.create_and_post_market_order,
                order_args,
                options=options, order_type=OrderType.FOK,
                defer_exec=defer_exec,
            )
        except Exception as e:
            logging.info(f"Failed to place Poly order: {e}")
            self.append_trade_csv({
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "exchange": "POLYMARKET",
                "asset_id": token_id,
                "side": enum_name(side),
                "price": price,
                "size": volume,
                "status": "ERROR",
                "defer_exec": os.getenv("POLY_DEFER_EXEC", "").lower() in {"1", "true", "yes"},
                "error": str(e),
            })
            return None

        order_id = response.get("orderID")
        success = response.get("success")
        status_text = str(response.get("status", "")).lower()
        if success and status_text == "matched":
            order_status = OrderStatus.FILLED
            self.position_manager.poly_balance += self.balance_delta(price, volume, side, Exchange.POLYMARKET)
        elif success and status_text in {"live", "delayed"}:
            logging.warning(f"Polymarket order accepted but not immediately filled: ID {order_id} | Status: {status_text}")
            order_status = OrderStatus.OPEN
        else:
            order_status = OrderStatus.KILLED


        result = Order(external_order_id=order_id, status=order_status, exchange=Exchange.POLYMARKET, side=side,
                       price=price, size=volume, asset_id=token_id)

        logging.info(f"Polymarket Order Placed! ID: {order_id}, asset_id: {token_id}, price {price}, size{volume} | Status: {order_status} | API status: {status_text}")
        self.append_trade_csv({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "exchange": "POLYMARKET",
            "asset_id": token_id,
            "side": enum_name(side),
            "price": price,
            "size": volume,
            "status": enum_name(order_status),
            "external_order_id": order_id,
            "api_status": status_text,
            "defer_exec": os.getenv("POLY_DEFER_EXEC", "").lower() in {"1", "true", "yes"},
        })
        return result

    async def process_execution_queue(self):
        """
        Consume execution events, place both opening legs concurrently, record completed positions, and unwind lone fills.
        """
        while True:
            execution_event: ExecutionEvent = await self.execution_queue.get()

            size = int(execution_event.volume)
            if size < 1:
                logging.warning(f"Skipping execution event with invalid size: {execution_event.volume}")
                self.execution_queue.task_done()
                continue

            side = execution_event.order_side
            poly_id = execution_event.poly_id
            kalshi_id = execution_event.kalshi_id
            poly_price = execution_event.poly_price
            kalshi_price = execution_event.kalshi_price
            if side == OrderSide.BUY:
                poly_result, kalshi_result = await asyncio.gather(
                self.post_poly_order(token_id=poly_id,price=poly_price,side=OrderSide.BUY, volume=size),
                self.post_kalshi_order(token_id = kalshi_id, price=kalshi_price, side=OrderSide.BUY, volume=size))
                if poly_result is None or kalshi_result is None:
                    logging.info("Critical: One of the order tasks failed to return a result. Skipping event.")
                    if kalshi_result is not None:
                        if kalshi_result.status == OrderStatus.FILLED:
                            await self.close_filled_leg(kalshi_result)
                    elif poly_result is not None:
                        if poly_result.status == OrderStatus.FILLED:
                            await self.close_filled_leg(poly_result)
                elif kalshi_result.status == OrderStatus.FILLED and poly_result.status == OrderStatus.FILLED:
                    spread = (1 - execution_event.kalshi_price - execution_event.poly_price -
                              0.07 * kalshi_price * (1 - kalshi_price) - 0.03 * poly_price * (1 - poly_price))
                    pos = Position(poly_id=poly_id, kalshi_id=kalshi_id, entry_leg_kalshi=kalshi_result,
                                   entry_leg_poly=poly_result,
                                   size=size, spread_including_fees=spread, status=PositionStatus.OPENING)
                    pos.status = PositionStatus.OPEN
                    self.position_manager.add_position(pos)
                elif kalshi_result.status != OrderStatus.FILLED and poly_result.status == OrderStatus.FILLED:
                    await self.close_filled_leg(poly_result)
                elif kalshi_result.status == OrderStatus.FILLED and poly_result.status != OrderStatus.FILLED:
                    await self.close_filled_leg(kalshi_result)
                else:
                    logging.info(
                        f"Execution event did not fill both legs. Kalshi: {kalshi_result.status} | Poly: {poly_result.status}"
                    )

                self.position_manager.active_ids.discard(poly_id)
                self.position_manager.active_ids.discard(kalshi_id)
                self.execution_queue.task_done()


    async def close_filled_leg(self, order: Order):
        """
        Try to flatten a single filled leg by repeatedly posting the opposite side at the current top of book.
        """
        exchange = order.exchange
        if order.side == OrderSide.BUY:
            side = OrderSide.SELL
        else: side = OrderSide.BUY
        size = order.size
        id = order.asset_id
        retries = 0



        if exchange == Exchange.KALSHI:
            orderbook = self.market_holder.kalshi_orderbooks[id]
            status = OrderStatus.KILLED
            while status == OrderStatus.KILLED and retries < 25:
                logging.warning(f"Retrying close_filled_leg for {id} on {exchange} | Retry count: {retries}")
                top = orderbook.best_bid() if side == OrderSide.SELL else orderbook.best_ask()
                if top is None:
                    logging.error(f"Cannot close filled leg for {id} on {exchange}: empty book")
                    break

                price = top["price"]
                result = await self.post_kalshi_order(token_id=id, side=side,price=price,volume=int(size))
                if result is None:
                    logging.error(f"Failed unwind attempt for {id} on {exchange}; retrying")
                else:
                    status = result.status
                await asyncio.sleep(.1)
                retries += 1


        elif exchange == Exchange.POLYMARKET:
            logging.warning(f"Retrying close_filled_leg for {id} on {exchange} | Retry count: {retries}")
            orderbook = self.market_holder.poly_orderbooks[id]
            status = OrderStatus.KILLED
            while status == OrderStatus.KILLED and retries < 25:
                top = orderbook.best_bid() if side == OrderSide.SELL else orderbook.best_ask()
                if top is None:
                    logging.error(f"Cannot close filled leg for {id} on {exchange}: empty book")
                    break

                price = top["price"]
                result = await self.post_poly_order(token_id=id, side=side, price=price, volume=int(size))
                if result is None:
                    logging.error(f"Failed unwind attempt for {id} on {exchange}; retrying")
                else:
                    status = result.status
                await asyncio.sleep(.1)
                retries += 1



    def balance_delta(self, price, volume, side, exchange):
        """
        Calculate the signed cash balance change for a filled order after the exchange-specific fee estimate.
        """
        fees = 0.07 * price * (1-price) * volume if exchange == Exchange.KALSHI else 0.03 * price * (1-price) * volume
        if side == OrderSide.SELL:
            delta = price*volume - fees
        if side == OrderSide.BUY:
            delta = -price*volume - fees
        return delta
