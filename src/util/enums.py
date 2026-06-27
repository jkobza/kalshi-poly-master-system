from enum import Enum

class Exchange(Enum):
    """
    Enum for easily representing the two exchanges
    """
    KALSHI = 1
    POLYMARKET = 2

class PositionStatus(Enum):
    """
    Enum for easily representing the position status
    """
    OPENING = 1
    OPEN = 2
    CLOSING = 3
    CLOSED = 4
    FAILED = 5

class OrderStatus(Enum):
    """
    Enum for easily representing the order status
    """
    OPEN = 1
    FILLED = 2
    KILLED = 3
    CLOSED = 4

class OrderSide(Enum):
    """
    Enum for easily representing the order side
    """
    BUY = 1
    SELL = 2