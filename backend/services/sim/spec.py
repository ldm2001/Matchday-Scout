from dataclasses import dataclass
from typing import Protocol, Dict, Any


@dataclass(frozen=True)
class SimState:
    xg_for: float
    xg_against: float
    pass_for: float
    pass_against: float
    poss: float


class Rule(Protocol):
    def data(self, state: SimState) -> Dict[str, Any]:
        ...
