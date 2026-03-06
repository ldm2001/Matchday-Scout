# 전술 시뮬레이터
import pandas as pd
import numpy as np
from typing import Dict, List
from collections import Counter

class TacticalSimulator:
    def __init__(self, events_df: pd.DataFrame):
        # 시간순 이벤트 스레드 정렬
        self.events = events_df.sort_values(['game_id', 'period_id', 'time_seconds'])
        # 객체 생성과 동시에 전이 행렬 캐싱
        self.trans_mat()
    
    # 이벤트 간의 마르코프 체인 전이 확률(Transition Matrix) 행렬 구축
    def trans_mat(self):
        # 특정 이벤트 A -> B로 이어지는 횟수 카운터
        self.transitions = Counter()
        # 특정 이벤트 A 자체의 발생 횟수 카운터
        self.event_counts = Counter()
        
        # 각 경기별로 순회하며 연속된 이벤트 쌍 집계
        for game_id in self.events['game_id'].unique():
            game_events = self.events[self.events['game_id'] == game_id].reset_index(drop=True)
            for i in range(len(game_events) - 1):
                current = game_events.iloc[i]['type_name']
                next_event = game_events.iloc[i + 1]['type_name']
                self.transitions[(current, next_event)] += 1
                self.event_counts[current] += 1
    
    # from_event 직후에 to_event가 발생할 확률(0~1) 계산
    def trans_prob(self, from_event: str, to_event: str) -> float:
        count = self.event_counts.get(from_event, 0)
        return 0 if count == 0 else self.transitions.get((from_event, to_event), 0) / count
    
    # 특정 선수(빌드업 허브)를 강하게 압박했을 때의 기대 효과 시뮬레이션
    def hub_case(self, hub_player_id: int) -> Dict:
        # 해당 선수가 주도한 패스 이벤트만 추출
        player_passes = self.events[
            (self.events['player_id'] == hub_player_id) & (self.events['type_name'] == 'Pass')
        ]
        
        # 패스 데이터가 없으면 진행 불가
        if len(player_passes) == 0:
            return {'error': '해당 선수의 패스 데이터 없음'}
        
        # 기존 패스 성패 비율 계산
        results = player_passes['result_name'].value_counts()
        total = len(player_passes)
        success_rate = results.get('Successful', 0) / total
        failure_rate = results.get('Unsuccessful', 0) / total
        
        # 집중 압박 시도 시 패스 성공률 저하 가정치 (-15%p)
        pressing_effect = 0.15
        
        # 패스 실패 직후 일어나는 상황(역습, 걷어내기 등) 추적용 카운터
        pass_fail_followups = Counter()
        for game_id in player_passes['game_id'].unique():
            game_events = self.events[self.events['game_id'] == game_id].reset_index(drop=True)
            player_game_passes = player_passes[player_passes['game_id'] == game_id]
            for _, pass_event in player_game_passes.iterrows():
                # 실패한 패스일 경우에만
                if pass_event['result_name'] == 'Unsuccessful':
                    action_id = pass_event['action_id']
                    # 해당 패스 이후 3개의 연쇄 액션 관찰
                    next_events = game_events[game_events['action_id'] > action_id].head(3)
                    for _, next_event in next_events.iterrows():
                        pass_fail_followups[next_event['type_name']] += 1
        
        # 시나리오 A: 원래 하던 대로 냅둘 경우 (압박 없음)
        scenario_a = {
            'name': '압박 없음 (현재)', 'pass_success_rate': round(success_rate, 3),
            'pass_failure_rate': round(failure_rate, 3),
            'description': f"패스 성공률 {success_rate*100:.1f}%"
        }
        
        # 시나리오 B: 압박 전술 가동 시
        scenario_b = {
            'name': '압박 적용', 'pass_success_rate': round(max(0, success_rate - pressing_effect), 3),
            'pass_failure_rate': round(min(1, failure_rate + pressing_effect), 3),
            'description': f"예상 패스 성공률 {(success_rate - pressing_effect)*100:.1f}% (↓{pressing_effect*100:.0f}%p)"
        }
        
        # 패스 실패 후 가장 잘 나타나는 Top 5 반응 상황 통계화
        followup_probs = {}
        total_followups = sum(pass_fail_followups.values())
        if total_followups > 0:
            for event_type, count in pass_fail_followups.most_common(5):
                followup_probs[event_type] = round(count / total_followups, 3)
        
        # 리포트 반환
        return {
            'player_id': hub_player_id, 'total_passes': total,
            'scenario_a': scenario_a, 'scenario_b': scenario_b,
            'on_failure_followups': followup_probs,
            'recommendation': self.rec_note(success_rate, failure_rate, pressing_effect, pass_fail_followups)
        }
    
        # 전술 제안 자연어 코멘트 작성 헬퍼
    def rec_note(self, success_rate: float, failure_rate: float, pressing_effect: float, followups: Counter) -> str:
        # 압박으로 얻을 기대 이득이 10%를 넘기면 강한 권장
        rec = "✅ 적극 압박 권장: " if success_rate * pressing_effect > 0.1 else "⚠️ 선택적 압박 권장: "
        if followups:
            # 실패 후 가장 많이 발생한 후속 상황 기반 멘트 첨언
            top_followup = followups.most_common(1)[0][0]
            if top_followup in ['Interception', 'Recovery']: rec += "볼 탈취 가능성 높음"
            elif top_followup in ['Clearance', 'Pass']: rec += "롱볼 전환 예상, 세컨볼 대비 필요"
            elif top_followup in ['Carry', 'Duel']: rec += "드리블 돌파 시도 예상"
        return rec
    
        # 특정 전술 패턴을 중간에 끊었을(태클/커트 등) 때 일어날 일 모의 실험
    def pattern_gap(self, pattern_sequence: List[str], disruption_point: int) -> Dict:
        if disruption_point >= len(pattern_sequence):
            return {'error': '차단 포인트가 패턴 길이를 초과'}
        
        # 차단 이전까지의 정상 패턴 궤적
        before_disruption = pattern_sequence[:disruption_point]
        # 차단당한 목표 이벤트
        disrupted_event = pattern_sequence[disruption_point]
        
        # 끊어냈을 경우(태클 성공 시, 인터셉트 시 등) 이후 흐름 확률 분포 세팅
        possible_outcomes = {}
        for outcome in ['Tackle', 'Interception', 'Duel']:
            followups = {}
            for next_event in ['Recovery', 'Clearance', 'Pass', 'Carry', 'Out']:
                # 마르코프 체인 질의
                prob = self.trans_prob(outcome, next_event)
                # 5% 미만 희귀 상황은 무시
                if prob > 0.05: followups[next_event] = round(prob, 3)
            possible_outcomes[outcome] = followups
        
        return {
            'disrupted_at': disrupted_event, 'disruption_index': disruption_point,
            'pattern_before': before_disruption, 'possible_outcomes': possible_outcomes
        }
    
        # 상대 허브 선수를 노린 인과적 약점 공략(프레싱 체인) 스토리텔링 조립
    def vuln_chain(self, hub_player_id: int) -> Dict:
        # 허브 선수 압박 시뮬레이션 선행
        hub_scenario = self.hub_case(hub_player_id)
        if 'error' in hub_scenario: return hub_scenario
        
        # 3단계 인과 체인 제안
        chain = {
            'step1': {'action': "허브 선수 압박", 'expected_result': "패스 실패율 +15%p 증가"},
            'step2': {'action': "예상 반응", 'expected_result': self.main_note(hub_scenario['on_failure_followups'])},
            'step3': {'action': "기회 창출", 'expected_result': self.chance_note(hub_scenario['on_failure_followups'])}
        }
        
        return {
            'player_id': hub_player_id, 'vuln_chain': chain,
            'summary': self.chain_note(chain)
        }
    
    # 실패 직후 발생할 가장 확률 높은 반응에 대한 번역
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
    
    # 우리 팀이 취할 수 있는 기회 요약
    def chance_note(self, followups: Dict) -> str:
        if not followups: return "상황 판단 필요"
        if 'Interception' in followups or 'Recovery' in followups: return "⚡ 역습 기회 (볼 탈취 가능)"
        elif 'Clearance' in followups: return "🎯 세컨볼 회수 → 공격 전환"
        return "🔄 계속 압박 유지"
    
    # 3단계 체인 요약 문장 생성
    def chain_note(self, chain: Dict) -> str:
        return f"{chain['step1']['action']} → {chain['step2']['expected_result']} → {chain['step3']['expected_result']}"


# 외부에서 호출하는 API용 시뮬레이트 래퍼 함수
def tactic_sim(events_df: pd.DataFrame, hub_player_id: int) -> Dict:
    simulator = TacticalSimulator(events_df)
    return {
        'pressing_simulation': simulator.hub_case(hub_player_id),
        'vuln_chain': simulator.vuln_chain(hub_player_id)
    }
