import uuid
from src.state_classes.market_holder import MarketHolder
from order import OrderSide, OrderStatus, Order

class PositionManager:



    def __init__(self, market_holder:MarketHolder):
        self.positions = {}
        self.kalshi_orders = {} # Maps orderId to order
        self.poly_orders = {} # Maps orderId to order
        self.kalshi_orderId_to_position = {} # maps a specific order to its corresponding position
        self.poly_orderId_to_position = {} # maps a specific order to its corresponding position
        self.market = market_holder







