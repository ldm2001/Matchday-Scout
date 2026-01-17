# 시뮬레이션 API 라우터
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

import sys
sys.path.append('..')
from services.data_loader import team_events, match_events, teams
from services.match_simulator import prematch as prematch_job
from services.vaep_calculator import team_vals
from services.simulator import tactic_sim
from services.chance_analyzer import chance_log, match_log

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
        our_events = team_events(request.our_team_id, request.n_games)
        opponent_events = team_events(request.opponent_id, request.n_games)
        if len(our_events) == 0: raise HTTPException(status_code=404, detail="우리팀 데이터 없음")
        if len(opponent_events) == 0: raise HTTPException(status_code=404, detail="상대팀 데이터 없음")
        
        result = prematch_job(our_events, opponent_events)
        result['our_team_id'] = request.our_team_id
        result['opponent_id'] = request.opponent_id
        return result
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# 팀 VAEP 분석 - 액션 가치 분석
@router.get("/vaep/{team_id}")
def vaep(team_id: int, n_games: int = 5):
    try:
        events = match_events(team_id, n_games, include_opponent=True, normalize_mode="none", spadl=False)
        if len(events) == 0: raise HTTPException(status_code=404, detail="팀 데이터 없음")
        return team_vals(events, team_id)
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# 압박 시뮬레이션 - 특정 선수 압박 효과
@router.post("/pressing")
def pressing(request: PressingRequest):
    try:
        events = team_events(request.team_id, request.n_games)
        if len(events) == 0: raise HTTPException(status_code=404, detail="팀 데이터 없음")
        return tactic_sim(events, request.hub_player_id)
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# 상대팀 목록 (시뮬레이션용)
@router.get("/opponents")
def opponents():
    try:
        return {"teams": teams()}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# 최근 경기 결과 목록
@router.get("/matches")
def matches(team_id: int = None):
    try:
        return {"matches": match_log(team_id)}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# 경기 핵심 찬스 분석
@router.get("/matches/{game_id}/chances")
def chances(game_id: int):
    try:
        return chance_log(game_id)
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))
