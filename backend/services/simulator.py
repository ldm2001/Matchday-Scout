# 전술 시뮬레이터
import pandas as pd
import numpy as np
from typing import Dict, List
from collections import Counter


class TacticalSimulator:
    def __init__(self, events_df: pd.DataFrame):
        self.events = events_df.sort_values(['game_id', 'period_id', 'time_seconds'])
        self.trans_mat()
    
    # 이벤트 전이 확률 행렬 구축
    def trans_mat(self):
        self.transitions = Counter()
        self.event_counts = Counter()
        
        for game_id in self.events['game_id'].unique():
            game_events = self.events[self.events['game_id'] == game_id].reset_index(drop=True)
            for i in range(len(game_events) - 1):
                current = game_events.iloc[i]['type_name']
                next_event = game_events.iloc[i + 1]['type_name']
                self.transitions[(current, next_event)] += 1
                self.event_counts[current] += 1
    
    # 전이 확률 계산
    def trans_prob(self, from_event: str, to_event: str) -> float:
        count = self.event_counts.get(from_event, 0)
        return 0 if count == 0 else self.transitions.get((from_event, to_event), 0) / count
    
    # 특정 선수 압박 시 시나리오
    def hub_case(self, hub_player_id: int) -> Dict:
        player_passes = self.events[
            (self.events['player_id'] == hub_player_id) & (self.events['type_name'] == 'Pass')
        ]
        
        if len(player_passes) == 0:
            return {'error': '해당 선수의 패스 데이터 없음'}
        
        results = player_passes['result_name'].value_counts()
        total = len(player_passes)
        success_rate = results.get('Successful', 0) / total
        failure_rate = results.get('Unsuccessful', 0) / total
        pressing_effect = 0.15
        
        pass_fail_followups = Counter()
        for game_id in player_passes['game_id'].unique():
            game_events = self.events[self.events['game_id'] == game_id].reset_index(drop=True)
            player_game_passes = player_passes[player_passes['game_id'] == game_id]
            for _, pass_event in player_game_passes.iterrows():
                if pass_event['result_name'] == 'Unsuccessful':
                    action_id = pass_event['action_id']
                    next_events = game_events[game_events['action_id'] > action_id].head(3)
                    for _, next_event in next_events.iterrows():
                        pass_fail_followups[next_event['type_name']] += 1
        
        scenario_a = {
            'name': '압박 없음 (현재)', 'pass_success_rate': round(success_rate, 3),
            'pass_failure_rate': round(failure_rate, 3),
            'description': f"패스 성공률 {success_rate*100:.1f}%"
        }
        scenario_b = {
            'name': '압박 적용', 'pass_success_rate': round(max(0, success_rate - pressing_effect), 3),
            'pass_failure_rate': round(min(1, failure_rate + pressing_effect), 3),
            'description': f"예상 패스 성공률 {(success_rate - pressing_effect)*100:.1f}% (↓{pressing_effect*100:.0f}%p)"
        }
        
        followup_probs = {}
        total_followups = sum(pass_fail_followups.values())
        if total_followups > 0:
            for event_type, count in pass_fail_followups.most_common(5):
                followup_probs[event_type] = round(count / total_followups, 3)
        
        return {
            'player_id': hub_player_id, 'total_passes': total,
            'scenario_a': scenario_a, 'scenario_b': scenario_b,
            'on_failure_followups': followup_probs,
            'recommendation': self.rec_note(success_rate, failure_rate, pressing_effect, pass_fail_followups)
        }
    
    # 전술 제안 생성
    def rec_note(self, success_rate: float, failure_rate: float, pressing_effect: float, followups: Counter) -> str:
        rec = "✅ 적극 압박 권장: " if success_rate * pressing_effect > 0.1 else "⚠️ 선택적 압박 권장: "
        if followups:
            top_followup = followups.most_common(1)[0][0]
            if top_followup in ['Interception', 'Recovery']: rec += "볼 탈취 가능성 높음"
            elif top_followup in ['Clearance', 'Pass']: rec += "롱볼 전환 예상, 세컨볼 대비 필요"
            elif top_followup in ['Carry', 'Duel']: rec += "드리블 돌파 시도 예상"
        return rec
    
    # 패턴 중간 차단 시뮬레이션
    def pattern_gap(self, pattern_sequence: List[str], disruption_point: int) -> Dict:
        if disruption_point >= len(pattern_sequence):
            return {'error': '차단 포인트가 패턴 길이를 초과'}
        
        before_disruption = pattern_sequence[:disruption_point]
        disrupted_event = pattern_sequence[disruption_point]
        
        possible_outcomes = {}
        for outcome in ['Tackle', 'Interception', 'Duel']:
            followups = {}
            for next_event in ['Recovery', 'Clearance', 'Pass', 'Carry', 'Out']:
                prob = self.trans_prob(outcome, next_event)
                if prob > 0.05: followups[next_event] = round(prob, 3)
            possible_outcomes[outcome] = followups
        
        return {
            'disrupted_at': disrupted_event, 'disruption_index': disruption_point,
            'pattern_before': before_disruption, 'possible_outcomes': possible_outcomes
        }
    
    # 약점 체인 분석
    def vuln_chain(self, hub_player_id: int) -> Dict:
        hub_scenario = self.hub_case(hub_player_id)
        if 'error' in hub_scenario: return hub_scenario
        
        chain = {
            'step1': {'action': "허브 선수 압박", 'expected_result': "패스 실패율 +15%p 증가"},
            'step2': {'action': "예상 반응", 'expected_result': self.main_note(hub_scenario['on_failure_followups'])},
            'step3': {'action': "기회 창출", 'expected_result': self.chance_note(hub_scenario['on_failure_followups'])}
        }
        
        return {
            'player_id': hub_player_id, 'vuln_chain': chain,
            'summary': self.chain_note(chain)
        }
    
    # 주요 반응 예측
    def main_note(self, followups: Dict) -> str:
        if not followups: return "데이터 부족"
        top_event = max(followups, key=followups.get)
        prob = followups[top_event]
        reactions = {
            'Clearance': f"롱볼 전환 (확률 {prob*100:.0f}%)",
            'Recovery': f"볼 회수 시도 (확률 {prob*100:.0f}%)",
            'Interception': f"상대 인터셉트 (확률 {prob*100:.0f}%)",
            'Pass': f"빠른 패스 시도 (확률 {prob*100:.0f}%)",
            'Carry': f"드리블 돌파 (확률 {prob*100:.0f}%)"
        }
        return reactions.get(top_event, f"{top_event} (확률 {prob*100:.0f}%)")
    
    # 기회 유형 분석
    def chance_note(self, followups: Dict) -> str:
        if not followups: return "상황 판단 필요"
        if 'Interception' in followups or 'Recovery' in followups: return "⚡ 역습 기회 (볼 탈취 가능)"
        elif 'Clearance' in followups: return "🎯 세컨볼 회수 → 공격 전환"
        return "🔄 계속 압박 유지"
    
    # 체인 요약 생성
    def chain_note(self, chain: Dict) -> str:
        return f"{chain['step1']['action']} → {chain['step2']['expected_result']} → {chain['step3']['expected_result']}"


def tactic_sim(events_df: pd.DataFrame, hub_player_id: int) -> Dict:
    simulator = TacticalSimulator(events_df)
    return {
        'pressing_simulation': simulator.hub_case(hub_player_id),
        'vuln_chain': simulator.vuln_chain(hub_player_id)
    }
