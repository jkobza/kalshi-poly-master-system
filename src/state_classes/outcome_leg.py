from src.util.enums import Exchange
from src.state_classes.orderbook import Orderbook

from dataclasses import dataclass



@dataclass
class OutcomeLeg:
    exchange: Exchange
    asset_id: str
    outcome_key: str
    orderbook: Orderbook
    last_update_ts: float | None
    delay_ms: int
    side_id: str | None = None
    order_intent: str | None = None
