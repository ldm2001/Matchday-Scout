# VAEP 기반 액션 가치 분석기 (Simplified)
# 참조: Decroos et al., IJCAI 2019 / KDD 2018

import pandas as pd
import numpy as np
from typing import Dict, List
import math


def safe_float(value, default=0.0):
    if value is None:
        return default
    try:
        result = float(value)
        return default if math.isnan(result) or math.isinf(result) else result
    except:
        return default


# 위치 기반 가치 (골문 가까울수록 높음)
def position_value(x: float, y: float) -> float:
    x, y = safe_float(x, 50), safe_float(y, 34)
    x_value = (x / 105) ** 1.5
    y_value = 1 - (abs(y - 34) / 34 * 0.3)
    
    if x >= 88.5 and 13.84 <= y <= 54.16: box_bonus = 0.3
    elif x >= 99.5 and 24.84 <= y <= 43.16: box_bonus = 0.5
    else: box_bonus = 0
    
    return min(1.0, x_value * y_value + box_bonus)


# 액션 타입별 기본 가치
ACTION_VALUES = {
    'Shot': 0.15, 'Goal': 1.0, 'Shot_Freekick': 0.12,
    'Pass_Cross': 0.08, 'Dribble': 0.04,
    'Pass': 0.02, 'Pass_Corner': 0.05, 'Pass_Freekick': 0.03,
    'Pass Received': 0.01, 'Carry': 0.01,
    'Tackle': 0.03, 'Interception': 0.04, 'Clearance': 0.02, 'Block': 0.03,
    'Keeper_save': 0.08, 'Keeper_claim': 0.04, 'Keeper_punch': 0.03,
    'Foul': -0.02, 'Card': -0.05,
}

RESULT_MODIFIERS = {
    'Success': 1.0, 'Unsuccessful': 0.3, 'Blocked': 0.5,
    'Saved': 0.4, 'Goal': 2.0, 'Own Goal': -1.0,
}


# 개별 액션 가치 계산
def action_value(event: pd.Series) -> float:
    x, y = safe_float(event.get('start_x'), 50), safe_float(event.get('start_y'), 34)
    pos_val = position_value(x, y)
    
    action_type = str(event.get('type_name', ''))
    act_val = ACTION_VALUES.get(action_type, 0.01)
    result_mod = RESULT_MODIFIERS.get(str(event.get('result_name', 'Success')), 0.7)
    
    if action_type in ['Pass', 'Pass_Cross', 'Carry']:
        end_x = safe_float(event.get('end_x'), x)
        advancement = (end_x - x) / 105
        if advancement > 0: act_val *= (1 + advancement * 0.5)
    
    if action_type == 'Shot':
        distance = ((x - 105)**2 + (y - 34)**2) ** 0.5
        act_val *= max(0.1, 1 - (distance / 50))
    
    return round(pos_val * act_val * result_mod, 4)


# 팀 선수별 VAEP 분석
def player_vaep(events_df: pd.DataFrame) -> List[Dict]:
    player_stats = {}
    
    for _, event in events_df.iterrows():
        player_id = event.get('player_id')
        if pd.isna(player_id): continue
        
        player_id = int(player_id)
        if player_id not in player_stats:
            player_stats[player_id] = {
                'player_id': player_id,
                'player_name': str(event.get('player_name_ko', str(player_id))),
                'position': str(event.get('position_name', 'Unknown')),
                'total_vaep': 0.0, 'actions': 0,
                'offensive_vaep': 0.0, 'defensive_vaep': 0.0, 'passing_vaep': 0.0,
            }
        
        value = action_value(event)
        player_stats[player_id]['total_vaep'] += value
        player_stats[player_id]['actions'] += 1
        
        action_type = str(event.get('type_name', ''))
        if action_type in ['Shot', 'Goal', 'Dribble', 'Shot_Freekick']:
            player_stats[player_id]['offensive_vaep'] += value
        elif action_type in ['Tackle', 'Interception', 'Clearance', 'Block']:
            player_stats[player_id]['defensive_vaep'] += value
        elif 'Pass' in action_type:
            player_stats[player_id]['passing_vaep'] += value
    
    result = list(player_stats.values())
    for p in result:
        p['avg_vaep'] = round(p['total_vaep'] / max(p['actions'], 1), 4)
        p['total_vaep'] = round(p['total_vaep'], 2)
        p['offensive_vaep'] = round(p['offensive_vaep'], 2)
        p['defensive_vaep'] = round(p['defensive_vaep'], 2)
        p['passing_vaep'] = round(p['passing_vaep'], 2)
    
    result.sort(key=lambda x: x['total_vaep'], reverse=True)
    return result


# 팀 VAEP 요약 (API용)
def team_vaep_summary(events_df: pd.DataFrame, n_top: int = 10) -> Dict:
    players = player_vaep(events_df)
    team_total = sum(p['total_vaep'] for p in players)
    
    return {
        'team_total_vaep': round(team_total, 2),
        'top_players': players[:n_top],
        'top_offensive': sorted(players, key=lambda x: x['offensive_vaep'], reverse=True)[:5],
        'top_defensive': sorted(players, key=lambda x: x['defensive_vaep'], reverse=True)[:5],
        'methodology': 'Simplified VAEP (Decroos et al., 2019)'
    }
