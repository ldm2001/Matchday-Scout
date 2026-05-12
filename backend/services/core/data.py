# 데이터 로더 - 엑셀 파일 로드 및 캐싱
import hashlib
import pandas as pd
from pathlib import Path
from functools import lru_cache

# SPADL 액션 체계 매핑 및 팀 데이터 정규화 함수 임포트
from .spadl import team_norm, spadl_map

# 백엔드 최상위 경로 기준 3단계 위로 올라가 open_track 폴더를 데이터 디렉토리로 설정
DATA_DIR = Path(__file__).resolve().parents[3] / "open_track"

# 파일 내용 해시 (size, sha256-prefix). mtime은 재계산 트리거로만 사용해 머신 간 일관 보장.
@lru_cache(maxsize=8)
def _file_mark(path_str: str, _mtime_ns: int, size: int) -> tuple:
    h = hashlib.sha256()
    with open(path_str, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return (size, h.hexdigest()[:16])

def _path_mark(path: Path) -> tuple:
    try:
        st = path.stat()
    except FileNotFoundError:
        return (0, "")
    return _file_mark(str(path), st.st_mtime_ns, st.st_size)

# 파일 내용 기반 스탬프 (머신/체크아웃 시점에 무관)
def data_stamp() -> tuple:
    raw_mark = _path_mark(DATA_DIR / "raw_data.csv")
    match_mark = _path_mark(DATA_DIR / "match_info.csv")
    return (raw_mark, match_mark)

# 파일 상태 스탬프를 키로 사용하여 raw_data를 메모리에 캐싱 (최대 2개 버전 보관)
@lru_cache(maxsize=2)
def _raw(mark: tuple) -> pd.DataFrame:
    # utf-8-sig 인코딩으로 BOM을 처리하며 CSV 로드
    df = pd.read_csv(DATA_DIR / "raw_data.csv", encoding='utf-8-sig')
    # 컬럼명의 앞뒤 공백 및 잔여 BOM 문자를 제거하여 정제
    df.columns = df.columns.str.strip().str.replace('\ufeff', '')
    return df

# 최신 상태 스탬프를 발급받아 캐싱된 은닉 객체(_raw)를 호출하는 퍼사드 래퍼 함수
def raw() -> pd.DataFrame:
    return _raw(data_stamp())

# 경기 정보(match_info.csv)도 동일하게 스탬핑 기반으로 LRU 캐싱 처리
@lru_cache(maxsize=2)
def _matches(mark: tuple) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "match_info.csv", encoding='utf-8-sig')
    # 컬럼명 정제 로직 포함
    df.columns = df.columns.str.strip().str.replace('\ufeff', '')
    return df

# 외부에서 호출하는 경기 정보 로드 함수
def matches() -> pd.DataFrame:
    return _matches(data_stamp())

# 특정 팀이 참여한 최근 N경기의 이벤트들만 싹 다 뽑아오는 함수 (상대팀 이벤트 배제)
def team_events(team_id: int, n_games: int = 5) -> pd.DataFrame:
    # 전체 마스터 이벤트 풀 로드
    events = raw()
    # 전체 메타 경기 정보 풀 로드
    match_df = matches()
    
    # 대상 팀이 홈 또는 원정으로 참여한 경기들만 필터링하고 최신 날짜순 정렬
    team_matches = match_df[
        (match_df['home_team_id'] == team_id) | 
        (match_df['away_team_id'] == team_id)
    ].sort_values('game_date', ascending=False)
    
    # 최근 n_games 개수만큼만 경기를 뽑아서 ID 리스트업
    recent_matches = team_matches.head(n_games)['game_id'].tolist()
    
    # 전체 이벤트 중 방금 추려낸 최근 경기들에 속하면서, '해당 팀이 주체'인 이벤트만 발췌
    team_events = events[
        (events['game_id'].isin(recent_matches)) & 
        (events['team_id'] == team_id)
    ]
    
    return team_events

# 특정 팀의 최근 경기에 대한 이벤트를 포괄적으로 가져와 SPADL 변환 및 정규화를 거쳐 제공하는 메인 프로바이더
def match_events(
    team_id: int,
    n_games: int = 5,
    include_opponent: bool = True,  # 상대팀의 이벤트 궤적까지 같이 들고올지 여부 (수비 분석 등 필요시 True)
    normalize_mode: str = "team",   # 좌표를 해당 팀 공격 방향 기준으로 엎을지 여부 설정
    spadl: bool = True,             # 오픈트랙 액션을 SPADL 범용 액션 타입으로 덮어씌울지 여부
) -> pd.DataFrame:
    # 전체 이벤트 볼륨과 게임 메타데이터 로드
    events = raw()
    match_df = matches()

    # 타겟 팀이 참여한 경기 식별 및 내림차순(최신순) 정렬
    team_matches = match_df[
        (match_df["home_team_id"] == team_id) | (match_df["away_team_id"] == team_id)
    ].sort_values("game_date", ascending=False)
    
    # 지정된 경기수(n_games) 만큼의 경기 ID 슬라이싱
    recent_matches = team_matches.head(n_games)["game_id"].tolist()

    # 해당 경기들에 발생한 전체 이벤트 풀 복제 생성 (경고 방지용 copy)
    match_events = events[events["game_id"].isin(recent_matches)].copy()
    
    # 상대 팀의 액션을 빼고 오로지 자팀의 액션만 볼 거라면 필터링 추가 
    if not include_opponent:
        match_events = match_events[match_events["team_id"] == team_id]

    # 좌표 통일화: 항상 분석 대상 팀이 왼쪽->오른쪽으로 공격하도록 좌표를 뒤집거나 보정 (team 모드)
    if normalize_mode == "team":
        match_events = team_norm(match_events, team_id, match_df)
    elif normalize_mode != "none":
        # team이나 none 이외의 모드가 들어오면 예외 발생
        raise ValueError("normalize_mode must be 'team' or 'none'")
        
    # StatsBomb 등 타 체계 유사 변환: SPADL 스키마화 요청 시 변환 함수 파이프라이닝
    if spadl:
        match_events = spadl_map(match_events)
        
    # 전처리 완료된 데이터프레임 방출
    return match_events

# 경기 목록 메타데이터를 훑어서 고유한 전체 축구 팀의 ID와 이름 목록만 엑기스로 뽑아주는 함수
def teams() -> list:
    # 매치 데이터 로드
    match_df = matches()
    
    # 홈 팀 컬럼만 똑 떼어서 유니크한 조합 추출
    home_teams = match_df[['home_team_id', 'home_team_name_ko']].drop_duplicates()
    # 컬럼명을 범용적인 team_id, team_name으로 세탁
    home_teams.columns = ['team_id', 'team_name']
    
    # 어웨이 팀들에 대해서도 똑같이 작업수행
    away_teams = match_df[['away_team_id', 'away_team_name_ko']].drop_duplicates()
    away_teams.columns = ['team_id', 'team_name']
    
    # 홈/어웨이 팀셋을 세로로 병합(concat)하고 최종적으로 이름이 겹치는 녀석들 한 번 더 쳐냄
    all_teams = pd.concat([home_teams, away_teams]).drop_duplicates()
    
    # DataFrame 구조를 딕셔너리 리스트(JSON-like) 배열로 뽑아서 반환 (API 응답 친화적)
    return all_teams.to_dict('records')
