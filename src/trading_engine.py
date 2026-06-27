'''
General idea:
Create one marketholder instance: Singleton
Put all poly and kalshi market Ids that I find into 2 lists, and have websockets monitor them,
updating the order books as it goes.
When a price is updated, check opposing market, do spread math, and execute trade at min size between sides
Currently, do not have any logic for redeeming/selling before event closes. Just sit and wait and figure out after
'''
import asyncio
import logging
from pathlib import Path

from src.execution_engine import ExecutionEngine
from src.state_classes.market_holder import MarketHolder
from src.state_classes.position_manager import PositionManager
from src.kalshi_modules.generate_kalshi_credentials import get_kalshi_client
from src.polymarket_modules.generate_poly_credentials import get_poly_client
from src.kalshi_modules.kalshi_listeners import listen_kalshi_markets, get_kalshi_balance
from src.polymarket_modules.polymarket_listeners import listen_polymarket_markets, get_polymarket_balance
from src.strategy_engine import StrategyEngine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BOT_LOG_PATH = PROJECT_ROOT / "logs" / "bot.log"

def setup_logging():
    """
    Configure root logging for both console output and the persistent bot log.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Clean format for the console
    c_handler = logging.StreamHandler()
    c_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
    c_handler.setFormatter(c_format)

    # Detailed format for the log file
    BOT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    f_handler = logging.FileHandler(BOT_LOG_PATH)
    f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    f_handler.setFormatter(f_format)

    logger.addHandler(c_handler)
    logger.addHandler(f_handler)

async def main():
        """
        Build the shared market state, clients, queues, strategy, and execution workers, then run them together.
        """
        setup_logging()
        logging.info("Starting engine...")
        logging.info("Starting engine...")

        markets = MarketHolder()
        poly_client = get_poly_client()
        kalshi_client = get_kalshi_client()
        orderbook_update_process_queue = asyncio.Queue()
        execution_queue = asyncio.Queue()
        user_update_process_queue = asyncio.Queue()
        kalshi_balance = await get_kalshi_balance(kalshi_client)
        poly_balance = await get_polymarket_balance(poly_client)
        position_manager = PositionManager(markets, kalshi_balance, poly_balance)
        logging.info(f"Kalshi balance: ${kalshi_balance:.2f}")
        logging.info(f"Polymarket balance: ${poly_balance:.2f}")
        strategy_engine = StrategyEngine(market_holder=markets,position_manager=position_manager,
                                         orderbook_update_process_queue=orderbook_update_process_queue,
                                         user_update_process_queue=user_update_process_queue,
                                         execution_queue=execution_queue)
        execution_engine = ExecutionEngine(execution_queue=execution_queue,position_manager=position_manager,
                                           poly_client=poly_client,kalshi_client=kalshi_client, market_holder=markets,)


        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(listen_polymarket_markets(markets,orderbook_update_process_queue))
                tg.create_task( listen_kalshi_markets(markets, orderbook_update_process_queue))
                tg.create_task(strategy_engine.process_orderbook_updates())
                tg.create_task(execution_engine.process_execution_queue())
        except* Exception as e:
            logging.critical("Critical failure. Initiating emergency stop.", exc_info=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Shutting down engine...")
        logging.info("Shutting down engine...")
