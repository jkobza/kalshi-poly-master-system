from src.util.enums import Exchange
from src.state_classes.orderbook import Orderbook
from abc import ABC
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Leg():
    exchange: Exchange
    description: str
    orderbook: Orderbook
    est_start_date: datetime
    est_end_date: datetime



