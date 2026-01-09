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


def team_data(team_id: int, n_games: int = 5) -> pd.DataFrame:
    events = raw_data()
    matches = match_info()
    
    team_matches = matches[
        (matches['home_team_id'] == team_id) | 
        (matches['away_team_id'] == team_id)
    ].sort_values('game_date', ascending=False)
    
    recent_matches = team_matches.head(n_games)['game_id'].tolist()
    
    team_events = events[
        (events['game_id'].isin(recent_matches)) & 
        (events['team_id'] == team_id)
    ]
    
    return team_events


def teams_list() -> list:
    matches = match_info()
    
    home_teams = matches[['home_team_id', 'home_team_name_ko']].drop_duplicates()
    home_teams.columns = ['team_id', 'team_name']
    
    away_teams = matches[['away_team_id', 'away_team_name_ko']].drop_duplicates()
    away_teams.columns = ['team_id', 'team_name']
    
    all_teams = pd.concat([home_teams, away_teams]).drop_duplicates()
    return all_teams.to_dict('records')
