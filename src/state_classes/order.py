from dataclasses import dataclass
from src.util.enums import OrderSide, OrderStatus, Exchange

@dataclass
class Order:
    id: str
    exchange: Exchange
    side: OrderSide
    price: float
    status: OrderStatus
    original_size: float
    size_matched: float
