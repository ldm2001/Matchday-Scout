from typing import Dict, Any

from .spec import SimState, Rule


class HubPressure(Rule):
    key = "press_hub"

    def data(self, state: SimState) -> Dict[str, Any]:
        return {
            "key": self.key,
            "bonus": 0.05,
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


class SetpieceGuard(Rule):
    key = "counter_setpiece"

    def data(self, state: SimState) -> Dict[str, Any]:
        return {
            "key": self.key,
            "bonus": 0.03,
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


class PatternRoute(Rule):
    key = "exploit_pattern"

    def data(self, state: SimState) -> Dict[str, Any]:
        return {
            "key": self.key,
            "bonus": 0.04,
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


RULES = [HubPressure(), SetpieceGuard(), PatternRoute()]
RULE_MAP = {rule.key: rule for rule in RULES}
