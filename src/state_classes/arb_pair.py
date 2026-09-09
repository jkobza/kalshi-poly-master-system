from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.state_classes.exchange_legs import Leg


@dataclass
class ArbPair:
    """
    Complementary arb pair: shared event metadata + one or more venue legs.

    Strategy code iterates `legs` uniformly; venue-specific details live on Leg subclasses.
    """

    pair_id: str
    description: str
    legs: list[Leg] = field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None
    expiration_time: datetime | None = None
    group_id: str | None = None
