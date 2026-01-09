# 경기 시뮬레이터 - Pre-Match 승률 예측 및 What-If 분석
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from collections import Counter
import math


def safe_float(val, default=0.0):
    if val is None: return default
    try:
        result = float(val)
        return default if math.isnan(result) or math.isinf(result) else result
    except: return default


class MatchSimulator:
    def __init__(self, our_events: pd.DataFrame, opponent_events: pd.DataFrame):
        self.our_events = our_events
        self.opponent_events = opponent_events
        self._base_stats()
    
    # 기본 통계 계산
    def _base_stats(self):
        our_shots = len(self.our_events[self.our_events['type_name'] == 'Shot'])
        our_goals = len(self.our_events[(self.our_events['type_name'] == 'Shot') & (self.our_events['result_name'] == 'Goal')])
        self.our_shot_conversion = our_goals / max(our_shots, 1)
        
        opp_shots = len(self.opponent_events[self.opponent_events['type_name'] == 'Shot'])
        opp_goals = len(self.opponent_events[(self.opponent_events['type_name'] == 'Shot') & (self.opponent_events['result_name'] == 'Goal')])
        self.opp_shot_conversion = opp_goals / max(opp_shots, 1)
        
        our_passes = self.our_events[self.our_events['type_name'] == 'Pass']
        self.our_pass_success = len(our_passes[our_passes['result_name'] == 'Successful']) / max(len(our_passes), 1)
        opp_passes = self.opponent_events[self.opponent_events['type_name'] == 'Pass']
        self.opp_pass_success = len(opp_passes[opp_passes['result_name'] == 'Successful']) / max(len(opp_passes), 1)
        
        total_events = len(self.our_events) + len(self.opponent_events)
        self.our_possession = len(self.our_events) / max(total_events, 1)
    
    # 승률 예측
    def win_probability(self, tactics: Dict = None) -> Dict:
        attack_factor = self.our_shot_conversion / max(self.our_shot_conversion + self.opp_shot_conversion, 0.01)
        defense_factor = 1 - (self.opp_shot_conversion / max(self.our_shot_conversion + self.opp_shot_conversion + 0.01, 0.01))
        base_win_prob = (attack_factor * 0.4 + defense_factor * 0.35 + self.our_possession * 0.25)
        
        tactic_bonus, tactic_details = 0.0, []
        if tactics:
            if tactics.get('press_hub'):
                tactic_bonus += 0.05
                tactic_details.append({'name': '허브 압박', 'effect': '+5%p', 'description': '상대 빌드업 허브를 집중 압박하여 패스 성공률 저하'})
            if tactics.get('counter_setpiece'):
                tactic_bonus += 0.03
                tactic_details.append({'name': '세트피스 대응', 'effect': '+3%p', 'description': '상대 세트피스 패턴에 맞춤 대응 배치'})
            if tactics.get('exploit_pattern'):
                tactic_bonus += 0.04
                tactic_details.append({'name': '패턴 공략', 'effect': '+4%p', 'description': '분석된 상대 약점 패턴을 활용한 공격 루트'})
        
        final_win_prob = min(0.85, base_win_prob + tactic_bonus)
        draw_prob = 0.25 * (1 - abs(final_win_prob - 0.5) * 2)
        lose_prob = max(0.05, 1 - final_win_prob - draw_prob)
        
        return {
            'win': round(safe_float(final_win_prob * 100), 1), 'draw': round(safe_float(draw_prob * 100), 1),
            'lose': round(safe_float(lose_prob * 100), 1), 'base_win_prob': round(safe_float(base_win_prob * 100), 1),
            'tactic_bonus': round(safe_float(tactic_bonus * 100), 1), 'tactics_applied': tactic_details
        }
    
    # What-If 시나리오
    def what_if(self, scenario: str) -> Dict:
        base_prob = self.win_probability()
        scenarios = {
            'press_hub': {'name': '허브 압박 전술 적용', 'description': '상대 빌드업 허브(중앙 미드필더)를 집중 압박', 'tactics': {'press_hub': True}},
            'counter_setpiece': {'name': '세트피스 대응 강화', 'description': '상대 세트피스 패턴 분석 기반 맞춤 수비', 'tactics': {'counter_setpiece': True}},
            'exploit_pattern': {'name': '약점 패턴 공략', 'description': '상대 수비 약점 활용 공격 루트', 'tactics': {'exploit_pattern': True}},
            'all_tactics': {'name': '종합 전술 적용', 'description': '모든 분석 기반 전술 동시 적용', 'tactics': {'press_hub': True, 'counter_setpiece': True, 'exploit_pattern': True}}
        }
        selected = scenarios.get(scenario, scenarios['all_tactics'])
        new_prob = self.win_probability(selected['tactics'])
        return {
            'scenario': selected['name'], 'description': selected['description'],
            'before': base_prob, 'after': new_prob,
            'win_change': round(new_prob['win'] - base_prob['win'], 1),
            'recommendation': self._recommendation(base_prob, new_prob)
        }
    
    # 전술 추천 생성
    def _recommendation(self, before: Dict, after: Dict) -> str:
        win_change = after['win'] - before['win']
        if win_change >= 10: return "✅ 강력 추천: 이 전술 조합으로 승률이 크게 상승합니다."
        elif win_change >= 5: return "👍 추천: 전술 적용 시 승률 개선이 예상됩니다."
        elif win_change >= 0: return "ℹ️ 참고: 소폭의 승률 개선이 가능합니다."
        return "⚠️ 주의: 이 전술은 현재 상황에 적합하지 않을 수 있습니다."
    
    # 맞춤 전술 제안
    def tactical_suggestions(self) -> List[Dict]:
        suggestions = []
        if self.opp_pass_success > 0.75:
            suggestions.append({'priority': 1, 'tactic': '중원 압박 강화', 'reason': f'상대 패스 성공률 {self.opp_pass_success*100:.0f}%로 높음', 'expected_effect': '패스 성공률 -10~15% 예상', 'win_prob_change': '+5%p'})
        if self.opp_shot_conversion > 0.15:
            suggestions.append({'priority': 2, 'tactic': '수비 라인 낮추기', 'reason': f'상대 슈팅 전환율 {self.opp_shot_conversion*100:.0f}%로 높음', 'expected_effect': '슈팅 기회 차단', 'win_prob_change': '+3%p'})
        if self.our_possession < 0.45:
            suggestions.append({'priority': 3, 'tactic': '역습 집중 전술', 'reason': f'예상 점유율 {self.our_possession*100:.0f}%로 낮음', 'expected_effect': '빠른 전환 공격 활용', 'win_prob_change': '+4%p'})
        if not suggestions:
            suggestions.append({'priority': 1, 'tactic': '균형 잡힌 전술 유지', 'reason': '양팀 전력 균형', 'expected_effect': '안정적인 경기 운영', 'win_prob_change': '±0%p'})
        return sorted(suggestions, key=lambda x: x['priority'])


def pre_match_simulation(our_events: pd.DataFrame, opponent_events: pd.DataFrame) -> Dict:
    simulator = MatchSimulator(our_events, opponent_events)
    base_prob = simulator.win_probability()
    all_tactics_prob = simulator.win_probability({'press_hub': True, 'counter_setpiece': True, 'exploit_pattern': True})
    scenarios = [simulator.what_if(s) for s in ['press_hub', 'counter_setpiece', 'exploit_pattern', 'all_tactics']]
    return {
        'base_prediction': base_prob, 'optimal_prediction': all_tactics_prob,
        'win_improvement': round(all_tactics_prob['win'] - base_prob['win'], 1),
        'tactical_suggestions': simulator.tactical_suggestions(), 'scenarios': scenarios
    }
