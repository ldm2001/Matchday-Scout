# 데이터 로더 - 엑셀 파일 로드 및 캐싱
import pandas as pd
from pathlib import Path
from functools import lru_cache


DATA_DIR = Path(__file__).parent.parent.parent / "open_track"


@lru_cache(maxsize=1)
def raw_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "raw_data.csv", encoding='utf-8-sig')
    df.columns = df.columns.str.strip().str.replace('\ufeff', '')
    return df


@lru_cache(maxsize=1)
def match_info() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "match_info.csv", encoding='utf-8-sig')
    df.columns = df.columns.str.strip().str.replace('\ufeff', '')
    return df


@lru_cache(maxsize=64)
def _team_match_ids(team_id: int) -> tuple:
    matches = match_info()
    team_matches = matches[
        (matches['home_team_id'] == team_id) |
        (matches['away_team_id'] == team_id)
    ].sort_values('game_date', ascending=False)
    return tuple(team_matches['game_id'].tolist())


@lru_cache(maxsize=256)
def _team_data_cached(team_id: int, n_games: int) -> pd.DataFrame:
    events = raw_data()
    match_ids = _team_match_ids(team_id)[:n_games]
    if not match_ids:
        return events.iloc[0:0]

    team_events = events[
        (events['game_id'].isin(match_ids)) &
        (events['team_id'] == team_id)
    ]
    return team_events


def team_data(team_id: int, n_games: int = 5) -> pd.DataFrame:
    return _team_data_cached(int(team_id), int(n_games))


@lru_cache(maxsize=1)
def teams_list() -> list:
    matches = match_info()
    
    home_teams = matches[['home_team_id', 'home_team_name_ko']].drop_duplicates()
    home_teams.columns = ['team_id', 'team_name']
    
    away_teams = matches[['away_team_id', 'away_team_name_ko']].drop_duplicates()
    away_teams.columns = ['team_id', 'team_name']
    
    all_teams = pd.concat([home_teams, away_teams]).drop_duplicates()
    return all_teams.to_dict('records')


def clear_caches() -> None:
    raw_data.cache_clear()
    match_info.cache_clear()
    _team_match_ids.cache_clear()
    _team_data_cached.cache_clear()
    teams_list.cache_clear()
