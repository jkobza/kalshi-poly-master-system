from dataclasses import dataclass
from order import Order


@dataclass
class Position:
    kalshi_id: str
    poly_id: str
    entry_leg_kalshi: Order
    entry_leg_poly: Order
    exit_leg_kalshi: Order
    exit_leg_poly: Order
    size: float
    spread_including_fees: float