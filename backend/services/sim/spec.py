from dataclasses import dataclass
from typing import Protocol, Dict, Any


@dataclass(frozen=True)
class SimState:
    our_shot_conv: float
    opp_shot_conv: float
    our_pass_success: float
    opp_pass_success: float
    our_possession: float


class Rule(Protocol):
    def data(self, state: SimState) -> Dict[str, Any]:
        ...
