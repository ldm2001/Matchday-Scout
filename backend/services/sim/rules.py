# 시뮬레이션 기반 승패 확률 산출 시 개입 가능한 전술 '룰북(Rules)' 모음
from typing import Dict, Any
from .spec import SimState, Rule

# 룰 1: 중원 허브(Playmaker) 집중 방어 및 압박 룰
class HubPressure(Rule):
    key = "press_hub"

    def data(self, state: SimState) -> Dict[str, Any]:
        return {
            "key": self.key,
            "bonus": 0.05,  # 적용 시 승률 기여분(가중치)
            "detail": {
                "name": "허브 압박",
                "effect": "+5%p",
                "description": "상대 빌드업 허브를 집중 압박하여 패스 성공률 저하",
            },
            "scenario": {
                "name": "허브 압박 전술 적용",
                "description": "상대 빌드업 허브(중앙 미드필더)를 집중 압박",
            },
        }

# 룰 2: 세트피스 특화 방어 대응 룰
class SetpieceGuard(Rule):
    key = "counter_setpiece"

    def data(self, state: SimState) -> Dict[str, Any]:
        return {
            "key": self.key,
            "bonus": 0.03,  # 안정적 방어로 +3%p
            "detail": {
                "name": "세트피스 대응",
                "effect": "+3%p",
                "description": "상대 세트피스 패턴에 맞춤 대응 배치",
            },
            "scenario": {
                "name": "세트피스 대응 강화",
                "description": "상대 세트피스 패턴 분석 기반 맞춤 수비",
            },
        }

# 룰 3: 상대의 수비적 허점(패턴)을 노린 공격 전개 룰
class PatternRoute(Rule):
    key = "exploit_pattern"

    def data(self, state: SimState) -> Dict[str, Any]:
        return {
            "key": self.key,
            "bonus": 0.04,  # xG 상승 기대분 +4%p
            "detail": {
                "name": "패턴 공략",
                "effect": "+4%p",
                "description": "분석된 상대 약점 패턴을 활용한 공격 루트",
            },
            "scenario": {
                "name": "약점 패턴 공략",
                "description": "상대 수비 약점 활용 공격 루트",
            },
        }

# 글로벌 등록 룰셋 배열
RULES = [HubPressure(), SetpieceGuard(), PatternRoute()]
# 조회 최적화를 위한 딕셔너리 매핑 구조
RULE_MAP = {rule.key: rule for rule in RULES}
