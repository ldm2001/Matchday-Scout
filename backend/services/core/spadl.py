# SPADL 변환 및 데이터 정규화 모듈
from __future__ import annotations
from typing import Dict, Iterable, Optional, Set
import pandas as pd
import numpy as np

PITCH_LENGTH = 105.0 # 그라운드 규격: 가로(X축) 105미터
PITCH_WIDTH = 68.0 # 그라운드 규격: 세로(Y축) 68미터

# 오픈트랙 고유의 이벤트 명칭을 SPADL 범용 액션 타입으로 변환
SPADL_ACTION_MAP: Dict[str, Optional[str]] = {
    "Pass": "pass", # 일반 패스
    "Pass_Corner": "corner_crossed", # 코너킥 찬스 패스
    "Pass_Freekick": "freekick_crossed", # 프리킥 찬스 패스
    "Cross": "cross", # 오픈플레이 크로스
    "Throw-In": "throw_in", # 스로인
    "Goal Kick": "goal_kick", # 골킥
    "Carry": "dribble", # 드리블 전진
    "Take-On": "take_on", # 1대1 돌파 시도
    "Shot": "shot", # 슈팅
    "Goal": "shot", # 득점 (SPADL에선 슛의 성공 범주로 통합)
    "Foul": "foul", # 파울
    "Handball_Foul": "foul", # 핸드볼 파울
    "Tackle": "tackle", # 태클 시도
    "Interception": "interception", # 패스 커팅/가로채기
    "Intervention": "interception", # 수비적 개입
    "Recovery": "interception", # 루즈볼 소유권 획득
    "Clearance": "clearance", # 위험 지역 걷어내기
    "Aerial Clearance": "clearance", # 공중볼 경합 후 걷어내기
    "Block": "block", # 슈팅 블록
    "Duel": "duel", # 경합
    "Catch": "keeper_claim", # 골키퍼 캐칭
    "Parry": "keeper_save", # 골키퍼 처내기 세이브
    "Hit": "keeper_punch", # 골키퍼 펀칭
    "Error": "error", # 치명적 실수
    
    # 모델링에서 무시해야 할 비(非)행동적 상태값 필터링용 None 매핑
    "Pass Received": None, # 패스 수신 (Action의 결과물일 뿐 독립적 액션 아님)
    "Ball Received": None, # 볼 수신
    "Pause": None, # 경기 중단
    "Defensive Line Support": None, # 수비 라인 지원 움직임
    "Out": None, # 아웃
    "Offside": None, # 오프사이드 판정
}

# SPADL 결과 상태 매핑 딕셔너리
SPADL_RESULT_MAP: Dict[str, str] = {
    "Successful": "success", # 성공
    "Unsuccessful": "fail", # 실패
    "Off Target": "offtarget", # 유효슈팅 아님
    "On Target": "ontarget", # 유효슈팅
    "Blocked": "blocked", # 수비벽에 막힘
    "Goal": "goal", # 득점 완료
    "Yellow_Card": "yellow_card", # 경고
    "Direct_Red_Card": "red_card", # 다이렉트 퇴장
    "Second_Yellow_Card": "red_card", # 경고 누적 퇴장
    "Own Goal": "owngoal", # 자책골
}

# 결측치나 문자열 등 오염된 수치형 데이터를 안전하게 float로 변환하는 내부 공용 함수
def _num(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        f = float(value)
        # NaN이나 Inf 값이면 디폴트로 떨어뜨림
        if np.isnan(f) or np.isinf(f):
            return default
        return f
    # 캐스팅 실패 시 안전장치
    except Exception:
        return default

# 좌표 정규화: 항상 타겟 팀(team_id)이 홈팀의 방향을 갖도록 좌표계를 뒤집음
def team_norm(
    events: pd.DataFrame, team_id: int, matches: pd.DataFrame
) -> pd.DataFrame:
    # 원본 훼손 방지 Copy
    events = events.copy()
    if events.empty:
        return events

    # 주어진 경기 메타에서 타겟 팀이 어웨이쪽으로 배정된 원정 경기들의 식별자만 추출
    away_games: Set[int] = set(
        matches.loc[matches["away_team_id"] == team_id, "game_id"].astype(int).tolist()
    )
    # 원정 경기가 하나도 없으면 엎을 필요 없음
    if not away_games:
        return events

    # 현재 이벤트 뭉치 중 원정 경기에 해당하는 로우들만 마스킹
    mask = events["game_id"].isin(away_games)
    # 해당하는 이벤트가 없다면 스킵
    if not mask.any():
        return events

    # X축 공격 방향 반전 적용: Pitch Length 기준 보수 취하기
    for col in ("start_x", "end_x"):
        if col in events.columns:
            events.loc[mask, col] = PITCH_LENGTH - events.loc[mask, col].astype(float)
    # Y축 방향 반전 적용
    for col in ("start_y", "end_y"):
        if col in events.columns:
            events.loc[mask, col] = PITCH_WIDTH - events.loc[mask, col].astype(float)
    # X축 이동 방향 속도/변위량 음양 반전
    if "dx" in events.columns:
        events.loc[mask, "dx"] = -events.loc[mask, "dx"].astype(float)
    # Y축 이동 방향 속도/변위량 음양 반전
    if "dy" in events.columns:
        events.loc[mask, "dy"] = -events.loc[mask, "dy"].astype(float)

    # 항상 공격 방향이 왼쪽->오른쪽으로 고정된 이벤트 스키마 반환
    return events

# 양팀 교차 좌표 정규화: 기준 팀 상관 없이 '어웨이 지정 팀'의 방향을 일관되게 엎는 로직
def side_norm(events: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    # 훼손 방지 Copy
    events = events.copy()
    if events.empty:
        return events

    # 경기별 어웨이 팀 ID 매핑 딕셔너리 생성
    away_map = matches.set_index("game_id")["away_team_id"].to_dict()
    # 이벤트마다 속한 경기의 어웨이 팀 ID를 가져옴
    away_ids = events["game_id"].map(away_map)
    # 현재 볼 점유 및 액션 주체(team_id)가 어웨이 팀과 동일한 로우들만 마스킹
    mask = events["team_id"] == away_ids
    # 바꿀 대상 없으면 스킵
    if not mask.any():
        return events

    # 이 역시 어웨이 쪽의 X, Y 좌표 및 변위(dx, dy) 벡터들을 보수/역산 취해 뒤집음
    for col in ("start_x", "end_x"):
        if col in events.columns:
            events.loc[mask, col] = PITCH_LENGTH - pd.to_numeric(events.loc[mask, col], errors="coerce").fillna(0)
    for col in ("start_y", "end_y"):
        if col in events.columns:
            events.loc[mask, col] = PITCH_WIDTH - pd.to_numeric(events.loc[mask, col], errors="coerce").fillna(0)
    if "dx" in events.columns:
        events.loc[mask, "dx"] = -pd.to_numeric(events.loc[mask, "dx"], errors="coerce").fillna(0)
    if "dy" in events.columns:
        events.loc[mask, "dy"] = -pd.to_numeric(events.loc[mask, "dy"], errors="coerce").fillna(0)

    # 엎어진 데이터 반환
    return events

# SPADL 표준 규격 필드들(spadl_type, spadl_result 등)을 새롭게 컬럼으로 맵핑 생성해주는 파이프라인
def spadl_map(events: pd.DataFrame) -> pd.DataFrame:
    events = events.copy()
    if events.empty:
        return events

    # 액션 스트링 치환 헬퍼 (없으면 other)
    def action_map(t: object) -> Optional[str]:
        key = str(t) if t is not None else ""
        return SPADL_ACTION_MAP.get(key, "other")

    # 결과 스트링 치환 헬퍼 (없으면 unknown)
    def result_map(r: object) -> str:
        key = str(r) if r is not None else ""
        return SPADL_RESULT_MAP.get(key, "unknown")

    # 매핑 적용하여 신규 컬럼 배정
    events["spadl_type"] = events["type_name"].apply(action_map)
    events["spadl_result"] = events["result_name"].apply(result_map)
    
    # 여러 제조사의 서브 타입 컬럼명 변형을 커버하기 위한 다중 스캔
    subtype_col = None
    for col in ("subtype_name", "pass_subtype", "pass_subtype_name", "sub_type", "sub_type_name"):
        if col in events.columns:
            subtype_col = col
            break
    # 잡힌 컬럼으로 spadl_subtype 바인딩 
    if subtype_col:
        events["spadl_subtype"] = events[subtype_col].fillna("unknown").astype(str)
    else:
        # 없으면 메인 타입(이름)이라도 가져가서 씀
        events["spadl_subtype"] = events["type_name"].fillna("unknown").astype(str)
        
    # 신체 부위(발, 머리 등) 컬럼명 허용 후보들 스캔
    body_col = None
    for col in ("body_part", "body_part_name", "body_part_type", "body_part_name_en"):
        if col in events.columns:
            body_col = col
            break
    # 부위 정보 바인딩
    if body_col:
        events["spadl_body_part"] = events[body_col].fillna("unknown").astype(str)
    else:
        events["spadl_body_part"] = "unknown"
        
    # None으로 치환된(제외해야 하는) 비행동 이벤트들을 걸러내기 위한 식별자 플래그 부여
    events["is_action"] = events["spadl_type"].notna()
    
    # SPADL 스키마가 붙은 데이터프레임 방출
    return events

# 비-행동형(is_action=False) 쓰레기 데이터들을 솎아내고 진짜 행동(Action) 로우만 남기는 필터
def action_rows(events: pd.DataFrame) -> pd.DataFrame:
    # SPADL 매핑이 되어 있지 않다면 강제로 우선 수행
    if "spadl_type" not in events.columns:
        events = spadl_map(events)
    # None(스킵 대상)이 아닌 순수 SPADL 행동 타입 로우만 필터해서 반환
    return events[events["spadl_type"].notna()].copy()

# 이 이벤트가 득점(Goal)으로 귀결되었는지 판별하는 논리 플래그 함수
def goal_flag(event: pd.Series) -> bool:
    t = str(event.get("type_name", ""))
    r = str(event.get("result_name", ""))
    # 타입명이 슛이면서 이름이 Goal이거나, 결과가 Goal이면 True
    return t == "Goal" or r == "Goal"

# 특정 X, Y 좌표(주로 슈팅 위치)에서 상대방 골대 정중앙 간의 거리를 구하는 함수
def goal_dist(x: float, y: float) -> float:
    # 결측치 시 하프라인 중앙으로 처리
    x = _num(x, PITCH_LENGTH / 2)
    y = _num(y, PITCH_WIDTH / 2)
    # 피타고라스 정리(유클리드 거리) (상대 골대 X는 Pitch Length 끝라인, Y는 중앙 34.0)
    return float(np.hypot(PITCH_LENGTH - x, (PITCH_WIDTH / 2) - y))

# 특정 X, Y 좌표에서 상대방 골대(너비 7.32m) 양 끝 포스트를 바라보는 '골문 각도' 계산
def goal_angle(x: float, y: float) -> float:
    # 안전 보정
    x = _num(x, PITCH_LENGTH / 2)
    y = _num(y, PITCH_WIDTH / 2)
    # 골대와 슈터 정면까지의 직선 깊이(dx)
    dx = PITCH_LENGTH - x
    # 골대 중앙 축과 슈터 간의 좌우 이격 깊이(dy)
    dy = abs((PITCH_WIDTH / 2) - y)
    # 공식 골대 크기 미터
    goal_width = 7.32
    # 코사인 제2법칙 및 삼각함수를 풀기 위한 분모 유도
    denom = (dx * dx + dy * dy) - (goal_width / 2) ** 2
    # 골라인과 너무 가깝거나 위치 불량으로 데드존(0 이하) 발생 시 일자 180도로 임시 폴백
    if denom <= 0:
        return float(np.pi)
    # 역탄젠트 변환으로 가시 개방 각도(라디안) 최종 리턴
    return float(np.arctan2(goal_width * dx, denom))
