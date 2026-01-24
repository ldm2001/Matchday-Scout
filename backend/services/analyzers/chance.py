# 경기 결과 기반 핵심 찬스 분석
import pandas as pd
import numpy as np
import math
from typing import Dict, List
from ..core.data import raw, matches


def num(value, default=0.0):
    if value is None:
        return default
    if isinstance(value, (int, float)):
        if math.isnan(value) or math.isinf(value):
            return default
        return float(value)
    try:
        f = float(value)
        return default if math.isnan(f) or math.isinf(f) else f
    except:
        return default


def shot_ctx(shot: pd.Series, before_events: pd.DataFrame) -> Dict:
    shot_x = num(shot.get('start_x', 50), 50)
    shot_y = num(shot.get('start_y', 34), 34)
    result = str(shot.get('result_name', ''))
    
    distance = 105 - shot_x
    is_central = 25 <= shot_y <= 43
    is_in_box = shot_x >= 85 and 15 <= shot_y <= 53
    
    failure_reasons = []
    if distance > 25: failure_reasons.append("슈팅 거리가 너무 멀어 골키퍼 대응 시간 충분")
    if not is_central:
        failure_reasons.append("왼쪽 측면에서 슈팅 각도 좁음" if shot_y < 25 else "오른쪽 측면에서 슈팅 각도 좁음")
    if not is_in_box: failure_reasons.append("페널티 박스 밖에서 슈팅")
    if 'Blocked' in result: failure_reasons.append("수비수에게 슈팅 막힘")
    elif 'Off T' in result: failure_reasons.append("슈팅이 골대 벗어남")
    elif 'Saved' in result or 'Goal' not in result: failure_reasons.append("골키퍼가 막아냄")
    if not failure_reasons: failure_reasons.append("슈팅이 골로 연결되지 않음")
    
    suggestion_reason = []
    better_x, better_y = shot_x, shot_y
    
    if distance > 30: better_x, suggestion_reason = min(shot_x + 15, 92), ["슈팅 지점 15m 전진"]
    elif distance > 20: better_x, suggestion_reason = min(shot_x + 10, 90), ["슈팅 지점 10m 전진"]
    elif distance > 10: better_x, suggestion_reason = min(shot_x + 5, 95), ["페널티 박스 안쪽 침투"]
    
    if shot_y < 20: better_y, suggestion_reason = shot_y + 12, suggestion_reason + ["중앙으로 커팅"]
    elif shot_y > 48: better_y, suggestion_reason = shot_y - 12, suggestion_reason + ["중앙으로 커팅"]
    elif shot_y < 30: better_y = shot_y + 8
    elif shot_y > 38: better_y = shot_y - 8
    
    if ((better_x - shot_x)**2 + (better_y - shot_y)**2)**0.5 < 5:
        better_x = min(shot_x + 5, 95)
        better_y = min(shot_y + 5, 40) if shot_y < 34 else max(shot_y - 5, 28)
        if not suggestion_reason: suggestion_reason = ["슈팅 위치 조정"]
    
    if 'Blocked' in result: suggestion_reason.append("페인팅 동작으로 수비수 제치기")
    if not suggestion_reason: suggestion_reason = ["첫 터치 빠르게 하여 GK 반응시간 단축"]
    
    angle_f = 1.0 if is_central else 0.7
    dist_f = max(0.1, 1 - (distance / 50))
    orig_xg = dist_f * angle_f * 0.3
    
    new_dist = 105 - better_x
    new_central = 25 <= better_y <= 43
    new_xg = max(0.1, 1 - (new_dist / 50)) * (1.0 if new_central else 0.8) * 0.35
    
    return {
        'failure_reasons': failure_reasons,
        'suggestion_reason': suggestion_reason,
        'better_position': {'x': num(better_x, 85), 'y': num(better_y, 34)},
        'original_xg': num(orig_xg * 100, 5),
        'improved_xg': num(new_xg * 100, 10),
        'xg_improvement': num((new_xg - orig_xg) * 100, 2),
    }


def play_seq(team_events: pd.DataFrame, end_time: float, period: int, n_events: int = 5) -> List[Dict]:
    before_shot = team_events[(team_events['period_id'] == period) & 
        (team_events['time_seconds'] >= end_time - 15) & 
        (team_events['time_seconds'] < end_time)].sort_values('time_seconds').tail(n_events)
    
    return [{'time': num(e.get('time_seconds', 0)), 'player': str(e.get('player_name_ko', '')),
             'position': str(e.get('position_name', '')), 'action': str(e.get('type_name', '')),
             'result': str(e.get('result_name', '')), 'start_x': num(e.get('start_x', 0)),
             'start_y': num(e.get('start_y', 0)), 'end_x': num(e.get('end_x', 0)),
             'end_y': num(e.get('end_y', 0))} for _, e in before_shot.iterrows()]


def chance_log(game_id: int) -> Dict:
    match_df = matches()
    events = raw()
    
    match = match_df[match_df['game_id'] == game_id]
    if len(match) == 0:
        return {'error': '경기를 찾을 수 없습니다'}
    
    match = match.iloc[0]
    home_id, away_id = int(match['home_team_id']), int(match['away_team_id'])
    home_score, away_score = int(match['home_score']), int(match['away_score'])
    
    if home_score > away_score:
        result, loser_id, loser_name = 'home_win', away_id, match['away_team_name_ko']
    elif away_score > home_score:
        result, loser_id, loser_name = 'away_win', home_id, match['home_team_name_ko']
    else:
        result, loser_id, loser_name = 'draw', None, None
    
    game_events = events[events['game_id'] == game_id].copy()
    
    def key_set(team_id: int, team_events: pd.DataFrame, team_name: str, is_home: bool, limit: int = 2) -> List[Dict]:
        chances = []
        shots = team_events[team_events['type_name'].str.contains('Shot', na=False)]
        
        for _, shot in shots.iterrows():
            if 'Goal' in str(shot.get('result_name', '')): continue
            
            shot_time, period = shot['time_seconds'], shot['period_id']
            before_shot = team_events[(team_events['period_id'] == period) & 
                (team_events['time_seconds'] >= shot_time - 10) & 
                (team_events['time_seconds'] < shot_time)].sort_values('time_seconds')
            
            raw_x, raw_y = num(shot.get('start_x', 50), 50), num(shot.get('start_y', 34), 34)
            shot_x, shot_y = (105 - raw_x, 68 - raw_y) if not is_home else (raw_x, raw_y)
            
            shot_copy = shot.copy()
            shot_copy['start_x'], shot_copy['start_y'] = shot_x, shot_y
            ctx = shot_ctx(shot_copy, before_shot)
            seq = play_seq(team_events, shot_time, period)
            last = before_shot.iloc[-1] if len(before_shot) > 0 else None
            
            chances.append({
                'time': num(shot_time, 0),
                'time_display': f"{'전반' if period == 1 else '후반'} {int(shot_time // 60)}분",
                'period': int(period), 'player': str(shot.get('player_name_ko', '')),
                'player_position': str(shot.get('position_name', '')),
                'action': str(shot.get('type_name', '')), 'result': str(shot.get('result_name', '')),
                'original_situation': {'description': f"{shot.get('player_name_ko', '')} 선수 슈팅",
                    'position': {'x': shot_x, 'y': shot_y}, 'goal_dist': 105 - shot_x,
                    'zone': '페널티박스 내' if shot_x >= 85 and 15 <= shot_y <= 53 else '박스 외곽'},
                'failure_analysis': {'reasons': ctx['failure_reasons'], 'xg': ctx['original_xg']},
                'suggestion': {'type': 'better_position', 'target_position': ctx['better_position'],
                    'reasons': ctx['suggestion_reason'], 'description': ' / '.join(ctx['suggestion_reason']),
                    'expected_xg': ctx['improved_xg'], 'xg_improvement': f"+{ctx['xg_improvement']}%p"},
                'play_sequence': seq,
                'setup_play': {'player': str(last.get('player_name_ko', '')), 'action': str(last.get('type_name', '')),
                    'from_x': num(last.get('start_x', 0)), 'from_y': num(last.get('start_y', 0)),
                    'to_x': num(last.get('end_x', 0)), 'to_y': num(last.get('end_y', 0))} if last is not None else None,
                'position': {'x': shot_x, 'y': shot_y},
            })
            if len(chances) >= limit: break
        
        return chances[:limit]
    
    analysis = {
        'game_id': int(game_id), 'date': str(match['game_date']),
        'home_team': {'id': home_id, 'name': match['home_team_name_ko'], 'score': home_score},
        'away_team': {'id': away_id, 'name': match['away_team_name_ko'], 'score': away_score},
        'result': result, 'score': f"{home_score}-{away_score}", 'chances': []
    }
    
    if result == 'draw':
        home_events, away_events = game_events[game_events['team_id'] == home_id], game_events[game_events['team_id'] == away_id]
        analysis['chances'] = [
            {'team_id': home_id, 'team_name': match['home_team_name_ko'], 
             'key_moments': key_set(home_id, home_events, match['home_team_name_ko'], True, 1)},
            {'team_id': away_id, 'team_name': match['away_team_name_ko'],
             'key_moments': key_set(away_id, away_events, match['away_team_name_ko'], False, 1)}
        ]
        analysis['summary'] = f"무승부 ({home_score}-{away_score}): 양팀 결정적 찬스 분석"
    else:
        loser_events = game_events[game_events['team_id'] == loser_id]
        analysis['chances'] = [{'team_id': loser_id, 'team_name': loser_name,
            'key_moments': key_set(loser_id, loser_events, loser_name, loser_id == home_id, 2)}]
        analysis['summary'] = f"{loser_name} 패배 분석: 결과를 바꿀 수 있었던 찬스"
    
    return analysis


def match_log(team_id: int = None) -> List[Dict]:
    match_df = matches()
    if team_id:
        match_df = match_df[(match_df['home_team_id'] == team_id) | (match_df['away_team_id'] == team_id)]
    
    recent = match_df.sort_values('game_date', ascending=False).head(20)
    results = []
    for _, m in recent.iterrows():
        h, a = int(m['home_score']), int(m['away_score'])
        if h > a: result, text = 'home_win', f"{m['home_team_name_ko']} 승"
        elif a > h: result, text = 'away_win', f"{m['away_team_name_ko']} 승"
        else: result, text = 'draw', '무승부'
        
        results.append({'game_id': int(m['game_id']), 'date': str(m['game_date'])[:10],
            'home_team': m['home_team_name_ko'], 'away_team': m['away_team_name_ko'],
            'home_team_id': int(m['home_team_id']), 'away_team_id': int(m['away_team_id']),
            'score': f"{h}-{a}", 'result': result, 'result_text': text})
    
    return results
