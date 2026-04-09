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
from src.classes.market_holder import MarketHolder
from src.classes.position_manager import PositionManager
from strategy_engine import strategy_engine
from execution_engine import execution_engine
from src.kalshi_modules.generate_kalshi_credentials import get_kalshi_client
from src.polymarket_modules.generate_poly_credentials import get_poly_client
from src.kalshi_modules.kalshi_listeners import  listen_kalshi_markets
from src.polymarket_modules.polymarket_listeners import  listen_polymarket_markets

logging.basicConfig(
    filename='../logs/bot_nightly.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def main():
        print("Starting engine...")
        logging.info("Starting engine...")

        markets = MarketHolder()
        poly_client = get_poly_client()
        kalshi_client = get_kalshi_client()
        positions = PositionManager(markets, poly_client, kalshi_client)

        signal_process_queue = asyncio.Queue()
        order_process_queue = asyncio.Queue()

        await asyncio.gather(
            listen_polymarket_markets(markets,signal_process_queue),
            listen_kalshi_markets(markets, signal_process_queue),
            strategy_engine(signal_process_queue, order_process_queue, markets),
            execution_engine(order_process_queue, markets, positions)
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down engine...")
        logging.info("Shutting down engine...")