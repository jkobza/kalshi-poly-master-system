from dataclasses import dataclass, field

from src.state_classes.arb_pair import ArbPair


@dataclass
class ArbGroup:
    group_id: str
    label: str
    arb_pairs: list[ArbPair] = field(default_factory=list)
    active_position_ids: list = field(default_factory=list)
    enabled: bool = True
    current_exposure: float = 0.0
