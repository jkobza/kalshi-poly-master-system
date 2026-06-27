import uuid
from dataclasses import dataclass, field
from src.util.enums import OrderSide, OrderStatus, Exchange



@dataclass
class Order:
    """
    Order class contains a reference to a single order.
    :var external_order_id: Order id from the particular exchange
    :var asset_id: The asset_id of the market which the order is for
    :var exchange: The exchange which the order is for
    :var status: The status of the order
    :var side: The side of the order
    :var price: The price of the order
    :var size: The size of the order
    :var internal_order_id: The internal order id.
    """
    external_order_id: int
    asset_id: str
    exchange: Exchange
    side: OrderSide
    price: float
    status: OrderStatus
    size: float
    internal_order_id: int = field(default_factory=lambda: uuid.uuid4().int)