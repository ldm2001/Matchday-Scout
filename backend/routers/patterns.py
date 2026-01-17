# 패턴 분석 API 라우터
from fastapi import APIRouter, HTTPException
from typing import Optional
import math

import sys
sys.path.append('..')
from services.data_loader import team_events, match_events
from services.pattern_analyzer import team_pat, PhaseAnalyzer
from services.setpiece_analyzer import team_set
from services.network_analyzer import team_net
from services.team_analyzer import team_stats
from services.vaep_model import team_sum


def num(value, default=0.0):
    if value is None: return default
    try:
        f = float(value)
        return default if math.isnan(f) or math.isinf(f) else f
    except: return default


def txt(value, default=''):
    if value is None: return default
    s = str(value)
    return default if s.lower() in ('nan', 'none', 'null', '') else s


router = APIRouter()


# 팀 공격 패턴 분석
@router.get("/{team_id}")
def patterns(team_id: int, n_games: int = 5, n_patterns: int = 3):
    try:
        events = match_events(team_id, n_games, include_opponent=True, normalize_mode="team")
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        result = team_pat(events, team_id, n_patterns)
        return {'team_id': team_id, 'n_games_analyzed': n_games, 'total_events': len(events), 'patterns': result}
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# 팀의 Phase 분할 결과
@router.get("/{team_id}/phases")
def phases(team_id: int, n_games: int = 5):
    try:
        events = match_events(team_id, n_games, include_opponent=True)
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        analyzer = PhaseAnalyzer(events)
        phase_list = analyzer.phase_list()
        team_phases = [p for p in phase_list if int(p.iloc[0].get('team_id', -1)) == int(team_id)]
        
        summaries = []
        for i, phase in enumerate(team_phases[:20]):
            features = analyzer.phase_stats(phase)
            summaries.append({
                'phase_id': i, 'length': features['length'],
                'duration': round(features['duration'], 1), 'has_shot': features['shot_count'] > 0,
                'passes': features['pass_count'],
                'start_zone': analyzer.zone_tag(features['start_x'], features['start_y']),
                'event_sequence': features['event_sequence'][:100]
            })
        
        return {'team_id': team_id, 'n_games_analyzed': n_games, 'total_phases': len(team_phases), 'phases': summaries}
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# 특정 Phase 리플레이 데이터
@router.get("/{team_id}/phases/{phase_id}/replay")
def phase_data(team_id: int, phase_id: int, n_games: int = 5):
    try:
        events = match_events(team_id, n_games, include_opponent=True)
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        analyzer = PhaseAnalyzer(events)
        phase_list = analyzer.phase_list()
        team_phases = [p for p in phase_list if int(p.iloc[0].get('team_id', -1)) == int(team_id)]
        
        if phase_id >= len(team_phases):
            raise HTTPException(status_code=404, detail="Phase를 찾을 수 없습니다")
        
        phase = team_phases[phase_id]
        start_time = phase['time_seconds'].min()
        replay_data = {'phase_id': phase_id, 'events': []}
        
        for _, event in phase.iterrows():
            replay_data['events'].append({
                'time': num(event.get('time_seconds', 0) - start_time, 0),
                'type': txt(event.get('type_name'), '액션'),
                'player': txt(event.get('player_name_ko'), '선수'),
                'player_id': txt(event.get('player_id'), ''),
                'position': txt(event.get('position_name'), ''),
                'start_x': num(event.get('start_x', 0), 50),
                'start_y': num(event.get('start_y', 0), 34),
                'end_x': num(event.get('end_x', 0), 50),
                'end_y': num(event.get('end_y', 0), 34),
                'result': txt(event.get('result_name'), '')
            })
        
        return replay_data
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# 팀 강약점 AI 분석
@router.get("/{team_id}/analysis")
def team_note(team_id: int, n_games: int = 100):
    try:
        events = match_events(team_id, n_games, include_opponent=True)
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        patterns_result = team_pat(events, team_id, n_patterns=5)
        team_df = team_events(team_id, n_games)
        setpieces_result = team_set(team_df, n_top=4)
        hubs_result = team_net(team_df, n_hubs=3)
        hubs = hubs_result.get('hubs', []) if isinstance(hubs_result, dict) else hubs_result
        
        return team_stats(team_id, patterns_result, setpieces_result, hubs)
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# VAEP 분석 (Decroos et al., IJCAI 2019)
@router.get("/{team_id}/vaep")
def team_vals(team_id: int, n_games: int = 100, n_top: int = 10):
    try:
        events = match_events(team_id, n_games, include_opponent=True, normalize_mode="none", spadl=False)
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        return {'team_id': team_id, 'n_games_analyzed': n_games, **team_sum(events, team_id, n_top)}
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))
