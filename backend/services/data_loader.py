# 데이터 로더 - 엑셀 파일 로드 및 캐싱
import pandas as pd
from pathlib import Path
from functools import lru_cache

from .spadl import team_norm, spadl_map


DATA_DIR = Path(__file__).parent.parent.parent / "open_track"


@lru_cache(maxsize=1)
def raw() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "raw_data.csv", encoding='utf-8-sig')
    df.columns = df.columns.str.strip().str.replace('\ufeff', '')
    return df


@lru_cache(maxsize=1)
def matches() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "match_info.csv", encoding='utf-8-sig')
    df.columns = df.columns.str.strip().str.replace('\ufeff', '')
    return df


def team_events(team_id: int, n_games: int = 5) -> pd.DataFrame:
    events = raw()
    match_df = matches()
    
    team_matches = match_df[
        (match_df['home_team_id'] == team_id) | 
        (match_df['away_team_id'] == team_id)
    ].sort_values('game_date', ascending=False)
    
    recent_matches = team_matches.head(n_games)['game_id'].tolist()
    
    team_events = events[
        (events['game_id'].isin(recent_matches)) & 
        (events['team_id'] == team_id)
    ]
    
    return team_events


def match_events(
    team_id: int,
    n_games: int = 5,
    include_opponent: bool = True,
    normalize_mode: str = "team",
    spadl: bool = True,
) -> pd.DataFrame:
    events = raw()
    match_df = matches()

    team_matches = match_df[
        (match_df["home_team_id"] == team_id) | (match_df["away_team_id"] == team_id)
    ].sort_values("game_date", ascending=False)
    recent_matches = team_matches.head(n_games)["game_id"].tolist()

    match_events = events[events["game_id"].isin(recent_matches)].copy()
    if not include_opponent:
        match_events = match_events[match_events["team_id"] == team_id]

    if normalize_mode == "team":
        match_events = team_norm(match_events, team_id, match_df)
    elif normalize_mode != "none":
        raise ValueError("normalize_mode must be 'team' or 'none'")
    if spadl:
        match_events = spadl_map(match_events)
    return match_events


def teams() -> list:
    match_df = matches()
    
    home_teams = match_df[['home_team_id', 'home_team_name_ko']].drop_duplicates()
    home_teams.columns = ['team_id', 'team_name']
    
    away_teams = match_df[['away_team_id', 'away_team_name_ko']].drop_duplicates()
    away_teams.columns = ['team_id', 'team_name']
    
    all_teams = pd.concat([home_teams, away_teams]).drop_duplicates()
    return all_teams.to_dict('records')
