# 경기 시뮬레이터 - Pre-Match 승률 예측 및 What-If 분석
import pandas as pd
from typing import Dict, List
import math

from .spec import SimState, Rule
from .rules import RULES


def num(val, default=0.0):
    if val is None: return default
    try:
        result = float(val)
        return default if math.isnan(result) or math.isinf(result) else result
    except: return default


class MatchSimulator:
    def __init__(self, our_events: pd.DataFrame, opponent_events: pd.DataFrame, rules: List[Rule] | None = None):
        self.our_events = our_events
        self.opponent_events = opponent_events
        self.base_stats()
        self.rules = list(rules) if rules is not None else list(RULES)
        self.rule_keys = [rule.data(self.state).get("key") for rule in self.rules]
        self.rule_map = {key: rule for key, rule in zip(self.rule_keys, self.rules) if key}
    
    # 기본 통계 계산
    def base_stats(self):
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
        self.state = SimState(
            our_shot_conv=self.our_shot_conversion,
            opp_shot_conv=self.opp_shot_conversion,
            our_pass_success=self.our_pass_success,
            opp_pass_success=self.opp_pass_success,
            our_possession=self.our_possession,
        )
    
    # 승률 예측
    def win_prob(self, rules: List[Rule] | None = None) -> Dict:
        attack_factor = self.our_shot_conversion / max(self.our_shot_conversion + self.opp_shot_conversion, 0.01)
        defense_factor = 1 - (self.opp_shot_conversion / max(self.our_shot_conversion + self.opp_shot_conversion + 0.01, 0.01))
        base_win_prob = (attack_factor * 0.4 + defense_factor * 0.35 + self.our_possession * 0.25)
        
        tactic_bonus, tactic_details = 0.0, []
        for rule in rules or []:
            entry = rule.data(self.state)
            tactic_bonus += num(entry.get("bonus", 0))
            detail = entry.get("detail")
            if detail:
                tactic_details.append(detail)
        
        final_win_prob = min(0.85, base_win_prob + tactic_bonus)
        draw_prob = 0.25 * (1 - abs(final_win_prob - 0.5) * 2)
        lose_prob = max(0.05, 1 - final_win_prob - draw_prob)
        
        return {
            'win': round(num(final_win_prob * 100), 1), 'draw': round(num(draw_prob * 100), 1),
            'lose': round(num(lose_prob * 100), 1), 'base_win_prob': round(num(base_win_prob * 100), 1),
            'tactic_bonus': round(num(tactic_bonus * 100), 1), 'tactics_applied': tactic_details
        }
    
    # What-If 시나리오
    def case(self, scenario: str) -> Dict:
        base_prob = self.win_prob()
        if scenario == "all_tactics":
            label = "종합 전술 적용"
            desc = "모든 분석 기반 전술 동시 적용"
            rule_list = self.rules
        else:
            rule = self.rule_map.get(scenario)
            entry = rule.data(self.state) if rule else None
            label = entry.get("scenario", {}).get("name") if entry else "종합 전술 적용"
            desc = entry.get("scenario", {}).get("description") if entry else "모든 분석 기반 전술 동시 적용"
            rule_list = [rule] if rule else self.rules
        new_prob = self.win_prob(rule_list)
        return {
            'scenario': label, 'description': desc,
            'before': base_prob, 'after': new_prob,
            'win_change': round(new_prob['win'] - base_prob['win'], 1),
            'recommendation': self.rec_note(base_prob, new_prob)
        }
    
    # 전술 추천 생성
    def rec_note(self, before: Dict, after: Dict) -> str:
        win_change = after['win'] - before['win']
        if win_change >= 10: return "✅ 강력 추천: 이 전술 조합으로 승률이 크게 상승합니다."
        elif win_change >= 5: return "👍 추천: 전술 적용 시 승률 개선이 예상됩니다."
        elif win_change >= 0: return "ℹ️ 참고: 소폭의 승률 개선이 가능합니다."
        return "⚠️ 주의: 이 전술은 현재 상황에 적합하지 않을 수 있습니다."
    
    # 맞춤 전술 제안
    def tactic_set(self) -> List[Dict]:
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


def prematch(our_events: pd.DataFrame, opponent_events: pd.DataFrame) -> Dict:
    simulator = MatchSimulator(our_events, opponent_events)
    base_prob = simulator.win_prob()
    all_tactics_prob = simulator.win_prob(simulator.rules)
    scenarios = [simulator.case(s) for s in simulator.rule_keys + ["all_tactics"]]
    return {
        'base_prediction': base_prob, 'optimal_prediction': all_tactics_prob,
        'win_improvement': round(all_tactics_prob['win'] - base_prob['win'], 1),
        'tactical_suggestions': simulator.tactic_set(), 'scenarios': scenarios
    }
