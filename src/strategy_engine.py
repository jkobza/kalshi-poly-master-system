import logging
import time

from src.monitoring.kalshi_market_status import KalshiMarketStatusCache
from src.monitoring.opportunity_logger import OpportunityLogger, OpportunitySnapshot
from src.state_classes.market_holder import MarketHolder, MatchedPair
from src.state_classes.events import OrderbookUpdateEvent, ExecutionEvent
from src.util.enums import Exchange, OrderSide
from src.state_classes.position_manager import PositionManager

class StrategyEngine:
    def __init__(self, market_holder: MarketHolder, position_manager: PositionManager, orderbook_update_process_queue, user_update_process_queue,
                 execution_queue, opportunity_logger: OpportunityLogger | None = None,
                 market_status_cache: KalshiMarketStatusCache | None = None,
                 monitor_only: bool = False):
        """
        Store shared state, queues, sizing limits, and heartbeat counters used by the strategy loop.

        Opportunity logging is optional and injected so monitoring stays modular and reusable
        outside this engine. When monitor_only is True, spreads are logged but never queued
        for execution.
        """
        self.market_holder = market_holder
        self.position_manager = position_manager
        self.orderbook_update_process_queue = orderbook_update_process_queue
        self.user_update_process_queue = user_update_process_queue
        self.execution_queue = execution_queue
        self.opportunity_logger = opportunity_logger
        self.market_status_cache = market_status_cache
        self.monitor_only = monitor_only

        self.MAX_SIZE = 10
        self.MIN_TRADE_SIZE = 1
        self.MIN_NET_SPREAD = 0.01
        self.STATS_INTERVAL_SECONDS = 30
        self.poly_update_count = 0
        self.kalshi_update_count = 0
        self.incomplete_book_count = 0
        self.execution_signal_count = 0
        self.poly_sell_skip_count = 0
        self.last_stats_log = time.monotonic()


    async def process_orderbook_updates(self):
        """
        Consume orderbook update events and run opening logic for matched pairs without active or open positions.
        """
        while True:
            update: OrderbookUpdateEvent = await self.orderbook_update_process_queue.get()
            try:
                exchange = update.exchange
                asset_id = update.assetId
                if exchange == Exchange.KALSHI:
                    self.kalshi_update_count += 1
                else:
                    self.poly_update_count += 1

                pairs = self.market_holder.pairs_for(exchange, asset_id)
                for pair in pairs:
                    # Always observe the pair for opportunity logging, even when we skip trading.
                    self.log_opportunity_if_enabled(pair)

                    tickers = {pair.ticker_a, pair.ticker_b}
                    pair_is_active = bool(tickers & self.position_manager.active_ids)
                    pair_is_open = any(
                        self.position_manager.has_open_position_for_asset(t) for t in tickers
                    )

                    if pair_is_active or pair_is_open:
                        continue

                    # Live execution still only supports Kalshi ↔ Poly Global.
                    if (
                        not self.monitor_only
                        and pair.is_kalshi_poly_global
                    ):
                        self.opening_trade_logic(pair)
            except Exception:
                logging.exception("Failed to process orderbook update")
            finally:
                self.orderbook_update_process_queue.task_done()
                self.log_stats_if_due()

    def build_opportunity_snapshot(self, pair: MatchedPair) -> OpportunitySnapshot:
        """
        Adapt live orderbooks into a plain OpportunitySnapshot for the monitoring package.
        """
        book_a = self.market_holder.get_orderbook(pair.exchange_a, pair.ticker_a)
        book_b = self.market_holder.get_orderbook(pair.exchange_b, pair.ticker_b)

        best_a = book_a.best_ask() if book_a else None
        best_b = book_b.best_ask() if book_b else None

        ask_a = best_a["price"] if best_a else None
        ask_b = best_b["price"] if best_b else None
        vol_a = float(best_a["volume"]) if best_a else 0.0
        vol_b = float(best_b["volume"]) if best_b else 0.0

        net_spread = None
        if ask_a is not None and ask_b is not None and pair.is_kalshi_poly_global:
            # Fee model is Kalshi + Poly Global specific today.
            kalshi_price = ask_a if pair.exchange_a == "kalshi" else ask_b
            poly_price = ask_b if pair.exchange_a == "kalshi" else ask_a
            net_spread = self.calculate_spread_net_fees(poly_price=poly_price, kalshi_price=kalshi_price)
        elif ask_a is not None and ask_b is not None:
            net_spread = 1.0 - ask_a - ask_b

        game_status = "unknown"
        kalshi_id = pair.kalshi_ticker()
        if self.market_status_cache is not None and kalshi_id:
            game_status = self.market_status_cache.get(kalshi_id)

        return OpportunitySnapshot(
            pair_id=pair.pair_id,
            exchange_a=pair.exchange_a,
            exchange_b=pair.exchange_b,
            ticker_a=pair.ticker_a,
            ticker_b=pair.ticker_b,
            side_a=pair.side_a,
            side_b=pair.side_b,
            ask_a=ask_a,
            ask_b=ask_b,
            ask_a_volume=vol_a,
            ask_b_volume=vol_b,
            market_desc=pair.market_desc,
            game_status=game_status,
            net_spread=net_spread,
            min_net_spread=self.MIN_NET_SPREAD,
        )

    def log_opportunity_if_enabled(self, pair: MatchedPair) -> None:
        """
        Feed a plain snapshot into the injected opportunity logger, if one is configured.
        """
        if self.opportunity_logger is None:
            return
        try:
            event = self.opportunity_logger.observe(self.build_opportunity_snapshot(pair))
            if event is not None and event.event in {"opened", "closed"}:
                logging.info(
                    "Opportunity %s | %s | duration=%.3fs | net_spread=%s | potential_win_total=%s",
                    event.event,
                    event.key,
                    event.duration_seconds,
                    event.payload.get("net_spread", ""),
                    event.payload.get("potential_win_total", ""),
                )
        except Exception:
            logging.exception("Failed to log opportunity for pair %s", pair.pair_id)

    def opening_trade_logic(self, pair: MatchedPair):
        """
        Compare the best asks for a matched Kalshi/Polymarket pair and queue an opening trade when net spread is positive.
        """
        kalshi_id = pair.kalshi_ticker()
        poly_id = pair.poly_ticker()
        if not kalshi_id or not poly_id:
            return

        kalshi_orderbook = self.market_holder.kalshi_orderbooks.get(kalshi_id)
        poly_orderbook = self.market_holder.poly_orderbooks.get(poly_id)

        if kalshi_orderbook is None or poly_orderbook is None:
            return

        kalshi_best_ask = kalshi_orderbook.best_ask()
        poly_best_ask = poly_orderbook.best_ask()

        if not all([kalshi_best_ask, poly_best_ask]):
            self.incomplete_book_count += 1
            return

        if (poly_best_ask["price"] + kalshi_best_ask["price"] < 1):
            spread = self.calculate_spread_net_fees(poly_price=poly_best_ask["price"], kalshi_price=kalshi_best_ask["price"])
            if spread > self.MIN_NET_SPREAD:
                logging.info(
                    "Spread Detected (net fees): %.4f | pair=%s | K_ID: %s | P_ID: %s",
                    spread, pair.pair_id, kalshi_id, poly_id,
                )
                self.create_and_place_opening_orders(
                    kalshi_orderbook=kalshi_orderbook,
                    poly_orderbook=poly_orderbook,
                    kalshi_id=kalshi_id,
                    poly_id=poly_id,
                )

    def calculate_spread_net_fees(self, poly_price:float, kalshi_price: float) \
            -> float:
        """
        Calculate the arbitrage spread after the configured Kalshi and Polymarket fee coefficients.
        :param kalshi_price: The kalshi ask price
        :param poly_price: The poly ask price
        :return: the spread net fees
        """
        spread = 0.0
        spread = 1 - poly_price - kalshi_price - 0.07*kalshi_price*(1-kalshi_price) - 0.03*poly_price*(1-poly_price)
        return spread

    def create_and_place_opening_orders(self, kalshi_orderbook, poly_orderbook,kalshi_id, poly_id ):
        """
        Size an opening trade, verify exchange balances, mark the pair active, and enqueue the execution event.
        """

        kalshi_price = kalshi_orderbook.best_ask()["price"]
        poly_price = poly_orderbook.best_ask()["price"]
        kalshi_volume = kalshi_orderbook.ask_volumes[kalshi_price]
        poly_volume = poly_orderbook.ask_volumes[poly_price]

        min_volume = min(poly_volume, kalshi_volume)
        if min_volume < self.MIN_TRADE_SIZE:
            return

        trade_volume = min(int(0.75 * min_volume), self.MAX_SIZE)
        poly_total_price = poly_price * trade_volume
        if poly_total_price < 1:
            return
        if trade_volume < self.MIN_TRADE_SIZE:
            return

        kalshi_total_price = 0.07*trade_volume*kalshi_price* (1-kalshi_price) + trade_volume*kalshi_price
        poly_total_price = 0.03*trade_volume*poly_price* (1-poly_price) + trade_volume*poly_price

        if kalshi_total_price > self.position_manager.kalshi_balance:
            logging.warning(f"Insufficient Kalshi Balance: {self.position_manager.kalshi_balance}")
            self.position_manager.active_ids.discard(kalshi_id)
            self.position_manager.active_ids.discard(poly_id)
            return
        if poly_total_price > self.position_manager.poly_balance:
            logging.warning(f"Insufficient Polymarket Balance: {self.position_manager.poly_balance}")
            self.position_manager.active_ids.discard(kalshi_id)
            self.position_manager.active_ids.discard(poly_id)
            return

        self.position_manager.active_ids.add(kalshi_id)
        self.position_manager.active_ids.add(poly_id)
        logging.info(
            f"Queueing ExecutionEvent: {trade_volume}  volume | K_ask: {kalshi_price} | P_ask: {poly_price} for kalshi: {kalshi_id}"
            f" Poly {poly_id}")
        self.execution_signal_count += 1
        self.execution_queue.put_nowait(ExecutionEvent(OrderSide.BUY,poly_price=poly_price,
                                                           kalshi_price=kalshi_price, poly_id=poly_id,
                                                           kalshi_id=kalshi_id,
                                                           volume=trade_volume))


    def log_stats_if_due(self):
        """
        Emit a periodic strategy heartbeat containing update, signal, active-pair, and open-position counts.
        """
        now = time.monotonic()
        if now - self.last_stats_log < self.STATS_INTERVAL_SECONDS:
            return

        self.last_stats_log = now
        logging.info(
            "Strategy heartbeat | kalshi_updates=%s | polymarket_updates=%s | incomplete_books=%s | execution_signals=%s | poly_sell_skips=%s | active_ids=%s | open_positions=%s",
            self.kalshi_update_count,
            self.poly_update_count,
            self.incomplete_book_count,
            self.execution_signal_count,
            self.poly_sell_skip_count,
            len(self.position_manager.active_ids),
            len(self.position_manager.open_positions),
        )
