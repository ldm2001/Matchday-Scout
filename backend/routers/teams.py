# 팀 관련 API 라우터
from fastapi import APIRouter, HTTPException
from typing import Optional

from services.core.data import teams as team_rows, team_events, matches as match_rows

router = APIRouter()


# K리그 팀 목록 조회
@router.get("/")
def teams():
    try:
        team_list = team_rows()
        return {"teams": team_list, "count": len(team_list)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 전체 팀 성적 개요
@router.get("/overview")
def overview():
    try:
        match_df = match_rows()
        team_list = team_rows()
        standings = []
        
        for team in team_list:
            team_id = team['team_id']
            team_name = team['team_name']
            
            home_matches = match_df[match_df['home_team_id'] == team_id]
            away_matches = match_df[match_df['away_team_id'] == team_id]
            
            wins, draws, losses = 0, 0, 0
            goals_for, goals_against = 0, 0
            
            for _, m in home_matches.iterrows():
                goals_for += m['home_score']
                goals_against += m['away_score']
                if m['home_score'] > m['away_score']: wins += 1
                elif m['home_score'] == m['away_score']: draws += 1
                else: losses += 1
            
            for _, m in away_matches.iterrows():
                goals_for += m['away_score']
                goals_against += m['home_score']
                if m['away_score'] > m['home_score']: wins += 1
                elif m['away_score'] == m['home_score']: draws += 1
                else: losses += 1
            
            total_matches = len(home_matches) + len(away_matches)
            points = wins * 3 + draws
            
            all_matches = match_df[
                (match_df['home_team_id'] == team_id) | (match_df['away_team_id'] == team_id)
            ].sort_values('game_date', ascending=False).head(5)
            
            form = []
            for _, m in all_matches.iterrows():
                is_home = m['home_team_id'] == team_id
                if is_home:
                    if m['home_score'] > m['away_score']: form.append('W')
                    elif m['home_score'] == m['away_score']: form.append('D')
                    else: form.append('L')
                else:
                    if m['away_score'] > m['home_score']: form.append('W')
                    elif m['away_score'] == m['home_score']: form.append('D')
                    else: form.append('L')
            
            standings.append({
                'team_id': team_id, 'team_name': team_name, 'played': total_matches,
                'wins': wins, 'draws': draws, 'losses': losses,
                'goals_for': int(goals_for), 'goals_against': int(goals_against),
                'goal_diff': int(goals_for - goals_against), 'points': points, 'form': form
            })
        
        standings.sort(key=lambda x: (-x['points'], -x['goal_diff'], -x['goals_for']))
        for i, team in enumerate(standings):
            team['rank'] = i + 1
        
        return {"standings": standings, "total_teams": len(standings)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 특정 팀 정보 조회
@router.get("/{team_id}")
def info(team_id: int):
    try:
        match_df = match_rows()
        home_matches = match_df[match_df['home_team_id'] == team_id]
        away_matches = match_df[match_df['away_team_id'] == team_id]
        
        if len(home_matches) == 0 and len(away_matches) == 0:
            raise HTTPException(status_code=404, detail="팀을 찾을 수 없습니다")
        
        team_name = home_matches.iloc[0]['home_team_name_ko'] if len(home_matches) > 0 else away_matches.iloc[0]['away_team_name_ko']
        total_matches = len(home_matches) + len(away_matches)
        
        all_matches = match_df[
            (match_df['home_team_id'] == team_id) | (match_df['away_team_id'] == team_id)
        ].sort_values('game_date', ascending=False)
        
        recent_matches = []
        for _, m in all_matches.head(5).iterrows():
            is_home = m['home_team_id'] == team_id
            recent_matches.append({
                'game_id': int(m['game_id']),
                'date': str(m['game_date']),
                'opponent': m['away_team_name_ko'] if is_home else m['home_team_name_ko'],
                'venue': 'H' if is_home else 'A',
                'score': f"{m['home_score']}-{m['away_score']}"
            })
        
        return {'team_id': team_id, 'team_name': team_name, 'total_matches': total_matches, 'recent_matches': recent_matches}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 팀의 이벤트 데이터 요약
@router.get("/{team_id}/events")
def events(team_id: int, n_games: int = 5):
    try:
        events = team_events(team_id, n_games)
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        event_stats = events['type_name'].value_counts().to_dict()
        player_stats = events.groupby(['player_id', 'player_name_ko']).size().reset_index(name='event_count')
        top_players = player_stats.nlargest(10, 'event_count').to_dict('records')
        
        return {'team_id': team_id, 'n_games': n_games, 'total_events': len(events),
                'event_types': event_stats, 'top_players': top_players}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
