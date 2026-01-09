# 패턴 분석 API 라우터
from fastapi import APIRouter, HTTPException
from typing import Optional
import math

import sys
sys.path.append('..')
from services.data_loader import team_data
from services.pattern_analyzer import team_patterns, PhaseAnalyzer
from services.setpiece_analyzer import team_setpieces
from services.network_analyzer import team_network
from services.team_analyzer import team_strengths
from services.vaep_analyzer import team_vaep_summary


def safe_float(value, default=0.0):
    if value is None: return default
    try:
        f = float(value)
        return default if math.isnan(f) or math.isinf(f) else f
    except: return default


def safe_str(value, default=''):
    if value is None: return default
    s = str(value)
    return default if s.lower() in ('nan', 'none', 'null', '') else s


router = APIRouter()


# 팀 공격 패턴 분석
@router.get("/{team_id}")
def patterns(team_id: int, n_games: int = 5, n_patterns: int = 3):
    try:
        events = team_data(team_id, n_games)
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        result = team_patterns(events, n_patterns)
        return {'team_id': team_id, 'n_games_analyzed': n_games, 'total_events': len(events), 'patterns': result}
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# 팀의 Phase 분할 결과
@router.get("/{team_id}/phases")
def phases(team_id: int, n_games: int = 5):
    try:
        events = team_data(team_id, n_games)
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        analyzer = PhaseAnalyzer(events)
        phase_list = analyzer.split_phases()
        
        summaries = []
        for i, phase in enumerate(phase_list[:20]):
            features = analyzer.phase_features(phase)
            summaries.append({
                'phase_id': i, 'length': features['length'],
                'duration': round(features['duration'], 1), 'has_shot': features['shot_count'] > 0,
                'passes': features['pass_count'],
                'start_zone': analyzer._pitch_zone(features['start_x'], features['start_y']),
                'event_sequence': features['event_sequence'][:100]
            })
        
        return {'team_id': team_id, 'n_games_analyzed': n_games, 'total_phases': len(phase_list), 'phases': summaries}
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# 특정 Phase 리플레이 데이터
@router.get("/{team_id}/phases/{phase_id}/replay")
def phase_replay(team_id: int, phase_id: int, n_games: int = 5):
    try:
        events = team_data(team_id, n_games)
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        analyzer = PhaseAnalyzer(events)
        phase_list = analyzer.split_phases()
        
        if phase_id >= len(phase_list):
            raise HTTPException(status_code=404, detail="Phase를 찾을 수 없습니다")
        
        phase = phase_list[phase_id]
        start_time = phase['time_seconds'].min()
        replay_data = {'phase_id': phase_id, 'events': []}
        
        for _, event in phase.iterrows():
            replay_data['events'].append({
                'time': safe_float(event.get('time_seconds', 0) - start_time, 0),
                'type': safe_str(event.get('type_name'), '액션'),
                'player': safe_str(event.get('player_name_ko'), '선수'),
                'player_id': safe_str(event.get('player_id'), ''),
                'position': safe_str(event.get('position_name'), ''),
                'start_x': safe_float(event.get('start_x', 0), 50),
                'start_y': safe_float(event.get('start_y', 0), 34),
                'end_x': safe_float(event.get('end_x', 0), 50),
                'end_y': safe_float(event.get('end_y', 0), 34),
                'result': safe_str(event.get('result_name'), '')
            })
        
        return replay_data
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# 팀 강약점 AI 분석
@router.get("/{team_id}/analysis")
def team_analysis(team_id: int, n_games: int = 100):
    try:
        events = team_data(team_id, n_games)
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        patterns_result = team_patterns(events, n_patterns=5)
        setpieces_result = team_setpieces(events, n_top=4)
        hubs_result = team_network(events, n_hubs=3)
        hubs = hubs_result.get('hubs', []) if isinstance(hubs_result, dict) else hubs_result
        
        return team_strengths(team_id, patterns_result, setpieces_result, hubs)
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# VAEP 분석 (Decroos et al., IJCAI 2019)
@router.get("/{team_id}/vaep")
def team_vaep(team_id: int, n_games: int = 100, n_top: int = 10):
    try:
        events = team_data(team_id, n_games)
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        return {'team_id': team_id, 'n_games_analyzed': n_games, **team_vaep_summary(events, n_top)}
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))
