from dataclasses import dataclass

from src.state_classes.outcome_leg import OutcomeLeg


@dataclass
class ArbPair:
    pair_id: str
    group_id: str
    leg_a: OutcomeLeg
    leg_b: OutcomeLeg

    
