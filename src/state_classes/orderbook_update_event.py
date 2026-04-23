from dataclasses import dataclass
from src.util.enums import Exchange

@dataclass
class OrderbookUpdateEvent():
    """
    Dataclass containing information about an order book update. This is used in the orderbook_update_process_queue
    """
    exchange: Exchange
    assetId: str

