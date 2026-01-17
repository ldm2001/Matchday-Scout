# 팀 강약점 AI 분석 서비스
from typing import Dict, List
from functools import lru_cache
import numpy as np

from services.data_loader import match_events, team_events
from services.pattern_analyzer import team_pat
from services.setpiece_analyzer import team_set
from services.network_analyzer import net_box


def team_stats(team_id: int, patterns: List[Dict], setpieces: List[Dict], hubs: List[Dict]) -> Dict:
    strengths = []
    weaknesses = []
    insights = []
    
    # 공격 패턴 분석
    if patterns:
        avg_shot_rate = np.mean([p.get('shot_conversion_rate', 0) for p in patterns])
        max_shot_rate = max([p.get('shot_conversion_rate', 0) for p in patterns])
        total_frequency = sum([p.get('frequency', 0) for p in patterns])
        
        if max_shot_rate > 0.25:
            strengths.append({'category': '공격', 'title': '높은 슈팅 전환율',
                'description': f'최고 {max_shot_rate*100:.0f}% 전환율의 위험한 공격 패턴 보유',
                'score': min(100, int(max_shot_rate * 300))})
        elif max_shot_rate < 0.1:
            weaknesses.append({'category': '공격', 'title': '낮은 결정력',
                'description': f'공격 패턴의 슈팅 전환율이 {max_shot_rate*100:.0f}%로 저조',
                'score': max(20, int(max_shot_rate * 300))})
        
        if total_frequency > 500:
            strengths.append({'category': '공격', 'title': '다양한 공격 루트',
                'description': f'{total_frequency}회의 다채로운 공격 시도',
                'score': min(100, int(total_frequency / 8))})
    
    # 세트피스 분석
    if setpieces:
        corner_routines = [s for s in setpieces if 'Corner' in s.get('type', '')]
        freekick_routines = [s for s in setpieces if 'Freekick' in s.get('type', '')]
        
        if corner_routines:
            avg_corner_rate = np.mean([c.get('shot_rate', 0) for c in corner_routines])
            if avg_corner_rate > 0.3:
                strengths.append({'category': '세트피스', 'title': '코너킥 위협',
                    'description': f'코너킥에서 {avg_corner_rate*100:.0f}% 슈팅 전환',
                    'score': min(100, int(avg_corner_rate * 200))})
            elif avg_corner_rate < 0.15:
                weaknesses.append({'category': '세트피스', 'title': '코너킥 효율 저조',
                    'description': f'코너킥 슈팅 전환율 {avg_corner_rate*100:.0f}%로 개선 필요',
                    'score': max(20, int(avg_corner_rate * 200))})
        
        if freekick_routines:
            avg_fk_rate = np.mean([f.get('shot_rate', 0) for f in freekick_routines])
            if avg_fk_rate > 0.25:
                strengths.append({'category': '세트피스', 'title': '프리킥 전문가',
                    'description': f'프리킥에서 {avg_fk_rate*100:.0f}% 슈팅 전환',
                    'score': min(100, int(avg_fk_rate * 200))})
    
    # 빌드업 허브 분석
    if hubs:
        top_hub = hubs[0] if hubs else None
        if top_hub:
            hub_score = top_hub.get('hub_score', 0)
            passes_made = top_hub.get('passes_made', 0)
            
            if hub_score > 0.8:
                strengths.append({'category': '빌드업', 'title': '핵심 플레이메이커',
                    'description': f"{top_hub.get('player_name', '선수')}가 공격 조율의 핵심",
                    'score': min(100, int(hub_score * 100))})
            
            if passes_made > 400:
                strengths.append({'category': '빌드업', 'title': '안정적 볼 순환',
                    'description': f'핵심 허브가 {passes_made}회 패스로 경기 지배',
                    'score': min(100, int(passes_made / 5))})
        
        if len(hubs) >= 2:
            hub_scores = [h.get('hub_score', 0) for h in hubs[:3]]
            if hub_scores[0] > hub_scores[1] * 1.5:
                weaknesses.append({'category': '빌드업', 'title': '허브 의존도 높음',
                    'description': f"1번 허브 {hubs[0].get('player_name', '')}에 과도하게 의존",
                    'score': 45})
    
    # 추가 약점 분석
    if patterns:
        if len(patterns) < 4:
            weaknesses.append({'category': '공격', 'title': '패턴 다양성 부족',
                'description': f'{len(patterns)}개의 한정된 공격 루트만 보유', 'score': 50})
        
        avg_duration = np.mean([p.get('avg_duration', 0) for p in patterns])
        if avg_duration > 40:
            weaknesses.append({'category': '공격', 'title': '느린 빌드업 템포',
                'description': f'평균 {avg_duration:.0f}초의 긴 빌드업, 역습에 취약 가능', 'score': 55})
    
    if setpieces:
        freekick_routines = [s for s in setpieces if 'Freekick' in s.get('type', '')]
        if freekick_routines:
            avg_fk_rate = np.mean([f.get('shot_rate', 0) for f in freekick_routines])
            if avg_fk_rate < 0.2:
                weaknesses.append({'category': '세트피스', 'title': '프리킥 활용 저조',
                    'description': f'프리킥 슈팅 전환율 {avg_fk_rate*100:.0f}%', 'score': 40})
    
    if hubs and len(hubs) >= 2:
        receives = [h.get('passes_received', 0) for h in hubs[:2]]
        if receives[0] > 0 and receives[1] > 0:
            ratio = receives[0] / max(receives[1], 1)
            if ratio > 1.8:
                weaknesses.append({'category': '빌드업', 'title': '패스 루트 예측 가능',
                    'description': '특정 선수로의 패스 집중, 상대 압박에 취약', 'score': 50})
    
    # 인사이트 생성
    if strengths:
        top_strength = max(strengths, key=lambda x: x['score'])
        insights.append(f"💪 가장 큰 강점: {top_strength['title']}")
    if weaknesses:
        top_weakness = max(weaknesses, key=lambda x: 100 - x['score'])
        insights.append(f"⚠️ 개선 필요: {top_weakness['title']}")
    if patterns and len(patterns) >= 3:
        insights.append(f"📊 {len(patterns)}개의 주요 공격 패턴 보유")
    if setpieces:
        insights.append(f"⚽ {len(setpieces)}개의 세트피스 루틴 분석됨")
    
    all_scores = [s['score'] for s in strengths] + [w['score'] for w in weaknesses]
    overall_score = int(np.mean(all_scores)) if all_scores else 50
    
    return {
        'team_id': team_id,
        'overall_score': overall_score,
        'strengths': sorted(strengths, key=lambda x: x['score'], reverse=True)[:3],
        'weaknesses': sorted(weaknesses, key=lambda x: x['score'])[:3],
        'insights': insights[:4],
        'summary': sum_text(strengths, weaknesses)
    }


def sum_text(strengths: List[Dict], weaknesses: List[Dict]) -> str:
    if not strengths and not weaknesses:
        return "분석할 데이터가 부족합니다."
    
    parts = []
    if strengths:
        strength_cats = list(set([s['category'] for s in strengths]))
        parts.append(f"{', '.join(strength_cats)} 분야에서 강점을 보입니다")
    if weaknesses:
        weak_cats = list(set([w['category'] for w in weaknesses]))
        parts.append(f"{', '.join(weak_cats)} 분야는 개선이 필요합니다")
    
    return ". ".join(parts) + "."


@lru_cache(maxsize=64)
def note_box(team_id: int, n_games: int, mark: tuple) -> Dict:
    events = match_events(team_id, n_games, include_opponent=True)
    if len(events) == 0:
        return {}
    patterns = team_pat(events, team_id, n_patterns=5)
    team_df = team_events(team_id, n_games)
    if len(team_df) == 0:
        return {}
    setpieces = team_set(team_df, n_top=4)
    hubs_result = net_box(team_id, n_games, 3, mark)
    hubs = hubs_result.get("hubs", []) if isinstance(hubs_result, dict) else hubs_result
    return team_stats(team_id, patterns, setpieces, hubs)
