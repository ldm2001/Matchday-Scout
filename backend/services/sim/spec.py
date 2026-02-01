# 시뮬레이션 타입 정의
from dataclasses import dataclass
from typing import Protocol, Dict, Any


# 시뮬레이션 상태 데이터 (xG, 패스, 점유율)
@dataclass(frozen=True)
class SimState:
    xg_for: float
    xg_against: float
    pass_for: float
    pass_against: float
    poss: float


# 전술 룰 프로토콜 - 상태 기반 전술 제안 반환
class Rule(Protocol):
    def data(self, state: SimState) -> Dict[str, Any]:
        ...
