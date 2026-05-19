# 시뮬레이션 API 라우터
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.core.data import team_events, teams, data_mark
from services.sim.match import prematch as prematch_job
from services.vaep.model import vals_box
from services.sim.tactic import tactic_sim
from services.analyzers.chance import chance_box, match_log

# 시뮬레이션 네임스페이스 라우터 할당
router = APIRouter()

# 클라이언트 요청 JSON 바디 스키마 모델
class PreMatchRequest(BaseModel):
    our_team_id: int # 우리 팀 고유 식별 명세 ID
    opponent_id: int # 맞대결 혹은 가상 대결 상대 팀 고유 ID
    n_games: Optional[int] = 5 # 기본 5경기

# 압박 및 허브 제어 전술 시뮬레이션 API 요청 모델
class PressingRequest(BaseModel):
    team_id: int # 적용할 대상 팀 ID
    hub_player_id: int # 집중 견제/압박을 가할 대상(Hub) 핵심 플레이어 ID
    n_games: Optional[int] = 5 # 시뮬레이션 기저 모델로 활용할 경기 수


# 프리매치 시뮬레이션 - 승률 예측 및 전술 제안
@router.post("/pre-match")
def prematch(request: PreMatchRequest):
    try:
        # 내 팀의 최근 경기 이벤트 원장 패치
        our_events = team_events(request.our_team_id, request.n_games)
        # 가상 상대 팀의 경기 이벤트 원장 패치
        opponent_events = team_events(request.opponent_id, request.n_games)
        
        # 어느 한 쪽이라도 경기 데이터가 없으면 시뮬 불가능 처리
        if len(our_events) == 0: raise HTTPException(status_code=404, detail="우리팀 데이터 없음")
        if len(opponent_events) == 0: raise HTTPException(status_code=404, detail="상대팀 데이터 없음")
        
        # 시뮬레이션 코어 엔진인 prematch_job에 양측 이벤트 릴레이
        result = prematch_job(our_events, opponent_events)
        # 분석 결과 객체에 클라이언트가 요청했던 팀 ID 메타데이터 동봉
        result['our_team_id'] = request.our_team_id
        result['opponent_id'] = request.opponent_id
        # 통합된 보고서 JSON 리턴
        return result
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# 팀 VAEP 분석 - 액션 가치 분석
@router.get("/vaep/{team_id}")
def vaep(team_id: int, n_games: int = 5):
    try:
        # 데이터 업데이트 핑거프린트 스탬프 도출
        mark = data_mark()
        # vals_box에 해당 팀/경기의 VAEP 스탯 산출/히트 요청
        result = vals_box(team_id, n_games, 5, mark)
        # 결과 실패 시 404
        if not result:
            raise HTTPException(status_code=404, detail="팀 데이터 없음")
        # 가공된 VAEP 통계 모음 딕셔너리 리턴
        return result
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# 압박 시뮬레이션 - 특정 선수 압박 효과
@router.post("/pressing")
def pressing(request: PressingRequest):
    try:
        # 대상 팀의 최신 이벤트 집합 패치
        events = team_events(request.team_id, request.n_games)
        # 이벤트 모음집 비어있으면 404
        if len(events) == 0: raise HTTPException(status_code=404, detail="팀 데이터 없음")
        
        # tactic_sim에 이벤트 뭉치와 타겟 플레이어 ID를 주입하여 돌린 시나리오 리턴
        return tactic_sim(events, request.hub_player_id)
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# 상대팀 목록 시뮬레이션용
@router.get("/opponents")
def opponents():
    try:
        # DB에서 전체 팀 목록 조회 후 teams 키로 박싱
        return {"teams": teams()}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# 최근 경기 결과 목록
@router.get("/matches")
def matches(team_id: int = None):
    try:
        # match_log에서 매치 요약본 패치
        return {"matches": match_log(team_id)}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# 경기 핵심 찬스 분석
@router.get("/matches/{game_id}/chances")
def chances(game_id: int):
    try:
        # 2-tier 캐시(L1+L2) 경유 찬스 분석 — 동일 game_id 재요청 시 디스크 hit
        return chance_box(game_id, data_mark())
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))
