# 시뮬레이션 API 라우터
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

import sys
sys.path.append('..')
from services.data_loader import team_data, teams_list
from services.match_simulator import pre_match_simulation
from services.vaep_calculator import team_vaep
from services.simulator import simulate_tactics
from services.chance_analyzer import missed_chances, match_list_results

router = APIRouter()

class PreMatchRequest(BaseModel):
    our_team_id: int
    opponent_id: int
    n_games: Optional[int] = 5

class PressingRequest(BaseModel):
    team_id: int
    hub_player_id: int
    n_games: Optional[int] = 5


# 프리매치 시뮬레이션 - 승률 예측 및 전술 제안
@router.post("/pre-match")
def prematch(request: PreMatchRequest):
    try:
        our_events = team_data(request.our_team_id, request.n_games)
        opponent_events = team_data(request.opponent_id, request.n_games)
        if len(our_events) == 0: raise HTTPException(status_code=404, detail="우리팀 데이터 없음")
        if len(opponent_events) == 0: raise HTTPException(status_code=404, detail="상대팀 데이터 없음")
        
        result = pre_match_simulation(our_events, opponent_events)
        result['our_team_id'] = request.our_team_id
        result['opponent_id'] = request.opponent_id
        return result
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# 팀 VAEP 분석 - 액션 가치 분석
@router.get("/vaep/{team_id}")
def vaep(team_id: int, n_games: int = 5):
    try:
        events = team_data(team_id, n_games)
        if len(events) == 0: raise HTTPException(status_code=404, detail="팀 데이터 없음")
        return team_vaep(events, team_id)
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# 압박 시뮬레이션 - 특정 선수 압박 효과
@router.post("/pressing")
def pressing(request: PressingRequest):
    try:
        events = team_data(request.team_id, request.n_games)
        if len(events) == 0: raise HTTPException(status_code=404, detail="팀 데이터 없음")
        return simulate_tactics(events, request.hub_player_id)
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# 상대팀 목록 (시뮬레이션용)
@router.get("/opponents")
def opponents():
    try:
        return {"teams": teams_list()}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# 최근 경기 결과 목록
@router.get("/matches")
def matches(team_id: int = None):
    try:
        return {"matches": match_list_results(team_id)}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# 경기 핵심 찬스 분석
@router.get("/matches/{game_id}/chances")
def chances(game_id: int):
    try:
        return missed_chances(game_id)
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))
