"""
Monitor-only entrypoint: stream orderbooks and log arb gaps to CSV.

Does not place orders. Requires Kalshi credentials for the market WebSocket
and optional status lookups. Polymarket market WebSocket is public.
"""
import asyncio
import logging
from pathlib import Path

from src.monitoring.kalshi_market_status import KalshiMarketStatusCache
from src.monitoring.opportunity_logger import OpportunityLogger
from src.state_classes.market_holder import MarketHolder
from src.state_classes.position_manager import PositionManager
from src.kalshi_modules.kalshi_listeners import listen_kalshi_markets
from src.polymarket_modules.polymarket_listeners import listen_polymarket_markets
from src.strategy_engine import StrategyEngine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BOT_LOG_PATH = PROJECT_ROOT / "logs" / "bot.log"


def setup_logging():
    """
    Configure root logging for both console output and the persistent bot log.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return

    c_handler = logging.StreamHandler()
    c_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")
    )

    BOT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    f_handler = logging.FileHandler(BOT_LOG_PATH)
    f_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    logger.addHandler(c_handler)
    logger.addHandler(f_handler)


async def main():
    """
    Run WebSocket listeners + strategy opportunity logging with trading disabled.
    """
    setup_logging()
    logging.info("Starting opportunity monitor (no order placement)...")

    markets = MarketHolder()
    orderbook_update_process_queue = asyncio.Queue()
    execution_queue = asyncio.Queue()
    user_update_process_queue = asyncio.Queue()

    # Balances unused in monitor mode; keep PositionManager happy.
    position_manager = PositionManager(markets, kalshi_balance=0.0, poly_balance=0.0)
    opportunity_logger = OpportunityLogger()
    market_status_cache = KalshiMarketStatusCache(ttl_seconds=60.0)
    logging.info("Opportunity CSV log: %s", opportunity_logger.path)
    logging.info("Watching %s Kalshi / %s Polymarket books",
                 len(markets.kalshi_orderbooks), len(markets.poly_orderbooks))

    strategy_engine = StrategyEngine(
        market_holder=markets,
        position_manager=position_manager,
        orderbook_update_process_queue=orderbook_update_process_queue,
        user_update_process_queue=user_update_process_queue,
        execution_queue=execution_queue,
        opportunity_logger=opportunity_logger,
        market_status_cache=market_status_cache,
        monitor_only=True,
    )

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(listen_polymarket_markets(markets, orderbook_update_process_queue))
            tg.create_task(listen_kalshi_markets(markets, orderbook_update_process_queue))
            tg.create_task(strategy_engine.process_orderbook_updates())
    except* Exception:
        logging.critical("Critical failure in opportunity monitor.", exc_info=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Shutting down opportunity monitor...")
