# 시뮬레이션 타입 모듈 
from dataclasses import dataclass
from typing import Protocol, Dict, Any

# 시뮬레이터를 굴리기 위한 현재 팀/상대 팀의 기본 스탯(xG, 패스, 점유율 등) 스냅샷 객체
@dataclass(frozen=True)
class SimState:
    xg_for: float # 득점 기대치
    xg_against: float # 실점 기대치
    pass_for: float # 패스 성공 스탯
    pass_against: float # 상대 패스 허용 스탯
    poss: float # 점유 비중 분배

# 각 전술 규칙들이 의무적으로 구현해야 하는 타이핑 표준 명세서
class Rule(Protocol):
    # SimState 문맥을 받아서 구체적인 보너스와 설명 파라미터를 넘기는 팩토리 메서드
    def data(self, state: SimState) -> Dict[str, Any]:
        ...
