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

OFFENSIVE_TYPES = {'Shot', 'Goal', 'Dribble', 'Shot_Freekick'}
DEFENSIVE_TYPES = {'Tackle', 'Interception', 'Clearance', 'Block'}
PASS_ADVANCE_TYPES = {'Pass', 'Pass_Cross', 'Carry'}

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


def _numeric_series(events_df: pd.DataFrame, column: str, default: float) -> pd.Series:
    series = events_df.get(column)
    if series is None:
        return pd.Series([default] * len(events_df), index=events_df.index, dtype='float64')
    return pd.to_numeric(series, errors='coerce').fillna(default)


def _string_series(events_df: pd.DataFrame, column: str, default: str) -> pd.Series:
    series = events_df.get(column)
    if series is None:
        return pd.Series([default] * len(events_df), index=events_df.index, dtype='object')
    return series.fillna(default).astype(str)


def _action_values(events_df: pd.DataFrame) -> np.ndarray:
    x = _numeric_series(events_df, 'start_x', 50.0).to_numpy()
    y = _numeric_series(events_df, 'start_y', 34.0).to_numpy()

    x_value = (x / 105) ** 1.5
    y_value = 1 - (np.abs(y - 34) / 34 * 0.3)

    box_bonus = np.zeros_like(x_value)
    box_mask = (x >= 88.5) & (y >= 13.84) & (y <= 54.16)
    box_bonus[box_mask] = 0.3
    box_mask_strict = (x >= 99.5) & (y >= 24.84) & (y <= 43.16)
    box_bonus[box_mask_strict] = 0.5

    pos_val = np.minimum(1.0, x_value * y_value + box_bonus)

    action_type = _string_series(events_df, 'type_name', 'nan')
    act_val = action_type.map(ACTION_VALUES).fillna(0.01).to_numpy(dtype='float64')

    result_name = _string_series(events_df, 'result_name', 'nan')
    result_mod = result_name.map(RESULT_MODIFIERS).fillna(0.7).to_numpy(dtype='float64')

    end_x = _numeric_series(events_df, 'end_x', np.nan)
    end_x = end_x.fillna(pd.Series(x, index=events_df.index)).to_numpy()
    advancement = (end_x - x) / 105
    pass_mask = action_type.isin(PASS_ADVANCE_TYPES).to_numpy()
    act_val = act_val * np.where(pass_mask & (advancement > 0), 1 + advancement * 0.5, 1.0)

    shot_mask = (action_type == 'Shot').to_numpy()
    distance = np.sqrt((x - 105) ** 2 + (y - 34) ** 2)
    shot_factor = np.maximum(0.1, 1 - (distance / 50))
    act_val = act_val * np.where(shot_mask, shot_factor, 1.0)

    return np.round(pos_val * act_val * result_mod, 4)


# 팀 선수별 VAEP 분석
def player_vaep(events_df: pd.DataFrame) -> List[Dict]:
    if events_df is None or len(events_df) == 0:
        return []

    player_series = events_df.get('player_id')
    if player_series is None:
        return []

    valid_mask = player_series.notna()
    if not valid_mask.any():
        return []

    cols = ['player_id', 'player_name_ko', 'position_name', 'type_name', 'result_name',
            'start_x', 'start_y', 'end_x', 'end_y']
    data = events_df.loc[valid_mask, cols].copy()
    data['value'] = _action_values(data)

    action_type = _string_series(data, 'type_name', 'nan')
    offensive_mask = action_type.isin(OFFENSIVE_TYPES)
    defensive_mask = action_type.isin(DEFENSIVE_TYPES)
    passing_mask = action_type.str.contains('Pass', na=False) & ~offensive_mask & ~defensive_mask

    grouped = data.groupby('player_id', sort=False)
    totals = grouped['value'].sum()
    actions = grouped['value'].size().astype(int)
    names = grouped['player_name_ko'].first().fillna('')
    positions = grouped['position_name'].first().fillna('Unknown')

    offensive = data.loc[offensive_mask].groupby('player_id')['value'].sum()
    defensive = data.loc[defensive_mask].groupby('player_id')['value'].sum()
    passing = data.loc[passing_mask].groupby('player_id')['value'].sum()

    summary = pd.DataFrame({
        'player_id': totals.index.astype(int),
        'player_name': names.reindex(totals.index).astype(str).values,
        'position': positions.reindex(totals.index).astype(str).values,
        'total_vaep': totals.values,
        'actions': actions.reindex(totals.index).fillna(0).astype(int).values,
        'offensive_vaep': offensive.reindex(totals.index).fillna(0).values,
        'defensive_vaep': defensive.reindex(totals.index).fillna(0).values,
        'passing_vaep': passing.reindex(totals.index).fillna(0).values,
    })

    summary['avg_vaep'] = (summary['total_vaep'] / summary['actions'].clip(lower=1)).round(4)
    summary['total_vaep'] = summary['total_vaep'].round(2)
    summary['offensive_vaep'] = summary['offensive_vaep'].round(2)
    summary['defensive_vaep'] = summary['defensive_vaep'].round(2)
    summary['passing_vaep'] = summary['passing_vaep'].round(2)

    summary = summary.sort_values('total_vaep', ascending=False)
    return summary.to_dict('records')


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
