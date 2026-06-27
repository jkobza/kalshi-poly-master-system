from dataclasses import dataclass, field
from src.state_classes.order import Order
from src.util.enums import PositionStatus
from typing import Optional, Dict, List
import uuid


@dataclass
class Position:
    """
    Dataclass containing info about a position. This is used in the strategy engine.

    :var kalshi_id: The unique identifier for the market on Kalshi.
    :var poly_id: The unique identifier for the market on Polymarket.
    :var entry_leg_kalshi: The initial order executed on Kalshi to open the position.
    :var entry_leg_poly: The initial order executed on Polymarket to open the position.
    :var exit_leg_kalshi: The order executed on Kalshi to close the position.
    :var exit_leg_poly: The order executed on Polymarket to close the position.
    :var size: The total size or volume of the position.
    :var status: The current lifecycle state of the position.
    :var spread_including_fees: The calculated spread between markets, accounting for transaction fees.
    :var pos_id: A unique integer identifier for the position record.
    """
    kalshi_id: str
    poly_id: str
    entry_leg_kalshi: Optional['Order'] = None
    entry_leg_poly: Optional['Order'] = None
    exit_leg_kalshi: Optional['Order'] = None
    exit_leg_poly: Optional['Order'] = None
    size: float = 0.0
    status: PositionStatus = PositionStatus.OPEN
    spread_including_fees: float = 0.0
    pos_id: int = field(default_factory=lambda: uuid.uuid4().int)
