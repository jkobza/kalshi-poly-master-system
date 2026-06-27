from dataclasses import dataclass
from src.util.enums import Exchange, OrderSide


@dataclass
class OrderbookUpdateEvent():
    """
    Dataclass containing information about an order book update. This is used in the orderbook_update_process_queue
    :var exchange: Exchange name
    :var assetId: Asset ID - on the specific exchange
    """
    exchange: Exchange
    assetId: str

@dataclass
class ExecutionEvent():
    """
    Dataclass containing the paired Kalshi/Polymarket opening trade to execute.
    :var order_side: Side to use for both legs in the current opening strategy.
    :var kalshi_price: Kalshi yes price for the trade.
    :var poly_price: Polymarket token price for the trade.
    :var poly_id: Polymarket token ID.
    :var kalshi_id: Kalshi market ticker.
    :var volume: Shared volume for both legs.
    """
    order_side: OrderSide
    kalshi_price: float
    poly_price: float
    poly_id: str
    kalshi_id: str
    volume: float
