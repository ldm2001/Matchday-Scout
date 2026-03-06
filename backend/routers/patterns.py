# 패턴 분석 API 라우터
from fastapi import APIRouter, HTTPException
from typing import Optional
import math
from services.core.data import match_events, data_stamp
from services.analyzers.pattern import team_pat, PhaseAnalyzer
from services.analyzers.team import note_box
from services.vaep.model import sum_box

# 결측치, 널, 문자열 꼬임 등 파싱 방어
def num(value, default=0.0):
    # 값이 아예 안 들어왔으면 지정된 기본값 리턴
    if value is None: return default
    try:
        # 일단 실수(float)로 구조적 형변환 시도
        f = float(value)
        # NaN이나 무한대 같은 비정상 수치라면 버리고 기본값 할당, 정상이면 통과
        return default if math.isnan(f) or math.isinf(f) else f
    # 아예 문자열 파싱 에러 등이 발생한 경우도 기본값으로 폴백 처리
    except: return default


# 문자형 데이터 안전 형변환 유틸리티 (NaN, Null 문자열 토큰 방어)
def txt(value, default=''):
    # 실제 None 타입이면 바로 가드
    if value is None: return default
    # 스트링 포맷으로 캐스팅
    s = str(value)
    # 판다스 처리 중 흔히 발생하는 쓰레기 더미 문자열들이면 모조리 기본값 치환
    return default if s.lower() in ('nan', 'none', 'null', '') else s

# 전술 패턴 전용 라우터 객체 구성
router = APIRouter()

# 팀 공격 패턴 분석
@router.get("/{team_id}")
def patterns(team_id: int, n_games: int = 5, n_patterns: int = 3):
    try:
        # 수비 방해 이벤트까지 포함하고, 분석용 정규화가 적용된 원시 이벤트 데이터 확보
        events = match_events(team_id, n_games, include_opponent=True, normalize_mode="team")
        # 해당 표본 경기들에 기록이 1건도 없으면 404 떨굼
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        # 코어 분석 모듈(DTW/K-Means 등 적용)을 통해 목표 N개 수만큼의 대표 패턴군 산출
        result = team_pat(events, team_id, n_patterns)
        # 통계 메타 모음과 함께 분석 결과를 JSON 형태로 정리하여 서빙
        return {'team_id': team_id, 'n_games_analyzed': n_games, 'total_events': len(events), 'patterns': result}
    # 기획된 HTTP 에러는 던지고, 이외 로직 에러는 500에 태워 보냄
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# 팀의 Phase 분할 결과
@router.get("/{team_id}/phases")
def phases(team_id: int, n_games: int = 5):
    try:
        # 경기 단위 연속성을 파악하기 위해 상대팀 이벤트도 다 긁어옴
        events = match_events(team_id, n_games, include_opponent=True)
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        # 페이즈 시퀀스 분석 인스턴스 초기화
        analyzer = PhaseAnalyzer(events)
        # 전체 이벤트를 소유권 체인별로 끊어서 분할 (리스트 속 데이터프레임 구조)
        phase_list = analyzer.phase_list()
        # 그 수많은 공방 국면 중, 조회 대상 '해당 팀이 주도권'을 가졌던 국면들만 추려냄
        team_phases = [p for p in phase_list if int(p.iloc[0].get('team_id', -1)) == int(team_id)]
        
        # 반환할 요약 정보 응답 배열 준비
        summaries = []
        # 프론트 부하를 고려해 가장 의미 짙었을 상위(최신) 20개 국면까지만 잘라서 순회 정보화
        for i, phase in enumerate(team_phases[:20]):
            # 1개의 국면 안에 속한 세부 이벤트들을 통계 수치화
            features = analyzer.phase_stats(phase)
            # 프론트 카드 UI용 요약 데이터 묶어 담기
            summaries.append({
                # 프론트 식별용 상위 ID
                'phase_id': i,
                # 해당 국면의 총 연속 이벤트 액션 발생 개수
                'length': features['length'],
                # 해당 국면이 지속된 타임라인(초)
                'duration': round(features['duration'], 1),
                # 슈팅으로 공격 작업이 마무리 되었는지 여부 플래그
                'has_shot': features['shot_count'] > 0,
                # 패스로 썰어나간 횟수
                'passes': features['pass_count'],
                # 공격 시발점이 어디었는지 좌표 라벨링(수비 진영, 상대 진영 등)
                'start_zone': analyzer.zone_tag(features['start_x'], features['start_y']),
                # 연속된 이벤트 흐름을 글자로 요약한 텍스트 릴레이 리스트 형태 (ex: 전진 패스 -> 드리블 -> 슛)
                'event_sequence': features['event_sequence'][:100]
            })
        
        # 총 국면 개수 등 메타데이터와 응답 배열을 말아서 리턴
        return {'team_id': team_id, 'n_games_analyzed': n_games, 'total_phases': len(team_phases), 'phases': summaries}
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# 특정 Phase 리플레이 데이터
@router.get("/{team_id}/phases/{phase_id}/replay")
def phase_data(team_id: int, phase_id: int, n_games: int = 5):
    try:
        # 똑같이 리스트를 우선 구축해야 하므로 이벤트 원장 조회
        events = match_events(team_id, n_games, include_opponent=True)
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        # 똑같이 페이즈 목록 썰어내기 진행
        analyzer = PhaseAnalyzer(events)
        phase_list = analyzer.phase_list()
        # 우리 팀 주도 페이즈만 거르기
        team_phases = [p for p in phase_list if int(p.iloc[0].get('team_id', -1)) == int(team_id)]
        
        # 요청한 국면 ID 인덱스가 발췌된 팀 페이즈 모음 인덱스 범위를 초과하는 경우 에러
        if phase_id >= len(team_phases):
            raise HTTPException(status_code=404, detail="Phase를 찾을 수 없습니다")
        
        # 콕 집어서 타겟 페이즈 데이터 프레임 1개만 할당
        phase = team_phases[phase_id]
        # 국면 첫 액션이 시작된 기준 시점 초단위 확보 (상대 시간 플레이어 구현 목적)
        start_time = phase['time_seconds'].min()
        # 프론트 구성 체계
        replay_data = {'phase_id': phase_id, 'events': []}
        
        # 타겟 국면 속 모든 로우 이벤트 액션을 시간순 순회
        for _, event in phase.iterrows():
            # 누락 및 쓰레기값 방어가 된 튼튼한 객체 구성
            replay_data['events'].append({
                # 국면 내 0초 베이스 상태로 정규화된 시퀀스 실행 경과 시간
                'time': num(event.get('time_seconds', 0) - start_time, 0),
                # 이벤트 명칭 문자
                'type': txt(event.get('type_name'), '액션'),
                # 관여자 플레이어의 한글 이름
                'player': txt(event.get('player_name_ko'), '선수'),
                # 관여자 고유 식별자
                'player_id': txt(event.get('player_id'), ''),
                # 미드필더 등 포지션 직무 스트링
                'position': txt(event.get('position_name'), ''),
                # 액션 출발점 물리 X 보정 처리 (기본 중앙 50 세팅)
                'start_x': num(event.get('start_x', 0), 50),
                # 액션 출발점 물리 Y 보정 처리 (기본 중앙 34 세팅)
                'start_y': num(event.get('start_y', 0), 34),
                # 액션 도착점(있는 경우) X
                'end_x': num(event.get('end_x', 0), 50),
                # 액션 도착점(있는 경우) Y
                'end_y': num(event.get('end_y', 0), 34),
                # 액션 성공 여부 명칭 문자열
                'result': txt(event.get('result_name'), '')
            })
        
        # 시뮬레이션용 배열 완성체 서빙
        return replay_data
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# 팀 강약점 AI 분석
@router.get("/{team_id}/analysis")
def team_note(team_id: int, n_games: int = 100):
    try:
        # 변경점 식별 스탬프
        mark = data_stamp()
        # 캐싱된 LLM 분석 노트 박스 질의하여 결과 뽑아옴
        result = note_box(team_id, n_games, mark)
        # 결과가 없으면 분석 실패
        if not result:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        # LLM이 작성한 평가 JSON 뭉치 서빙
        return result
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# VAEP 분석 
@router.get("/{team_id}/vaep")
def team_vals(team_id: int, n_games: int = 100, n_top: int = 10):
    try:
        # 데이터 갱신 타임 체크
        mark = data_stamp()
        # 캐시 레이어를 곁들인 코어 VAEP 모듈 점수 합산 로직 호출 (상위 n_top 만큼)
        result = sum_box(team_id, n_games, n_top, mark)
        # 실패하면 에러처리
        if not result:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        # 구조 분해 할당(Spread)으로 통계 조회 메타 데이터를 섞어 반환
        return {'team_id': team_id, 'n_games_analyzed': n_games, **result}
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))
