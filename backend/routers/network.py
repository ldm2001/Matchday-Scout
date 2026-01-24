# 네트워크 분석 API 라우터
from fastapi import APIRouter, HTTPException

from services.core.data import team_events, data_stamp
from services.analyzers.network import net_box, NetworkAnalyzer

router = APIRouter()


# 팀 패스 네트워크 분석 및 허브 탐지
@router.get("/{team_id}")
def network(team_id: int, n_games: int = 5, n_hubs: int = 2):
    try:
        mark = data_stamp()
        result = net_box(team_id, n_games, n_hubs, mark)
        if not result:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        return {
            'team_id': team_id, 'n_games_analyzed': n_games, 'hubs': result['hubs'],
            'network_stats': {'nodes': len(result['network']['nodes']), 'edges': len(result['network']['edges'])}
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 시각화용 네트워크 그래프 데이터
@router.get("/{team_id}/graph")
def graph(team_id: int, n_games: int = 5):
    try:
        mark = data_stamp()
        result = net_box(team_id, n_games, 2, mark)
        if not result:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        return {'team_id': team_id, 'n_games_analyzed': n_games, 'graph': result['network']}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 특정 허브 선수 상세 정보
@router.get("/{team_id}/hubs/{player_id}")
def hub_detail(team_id: int, player_id: int, n_games: int = 5):
    try:
        events = team_events(team_id, n_games)
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        analyzer = NetworkAnalyzer(events)
        analyzer.net_graph()
        cent = analyzer.cent()
        
        if player_id not in cent:
            raise HTTPException(status_code=404, detail="해당 선수를 찾을 수 없습니다")
        
        stats = cent[player_id]
        return {
            'team_id': team_id, 'player_id': player_id,
            'player_name': stats['name'], 'position': stats['position'],
            'stats': stats, 'key_connections': analyzer.link_set(player_id, 5),
            'disruption_impact': analyzer.impact_stat(player_id)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 모든 선수의 중심성 지표
@router.get("/{team_id}/centrality")
def cent_data(team_id: int, n_games: int = 5):
    try:
        events = team_events(team_id, n_games)
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        analyzer = NetworkAnalyzer(events)
        analyzer.net_graph()
        cent = analyzer.cent()
        
        players = [{'player_id': int(pid) if not isinstance(pid, str) else pid, **stats}
                   for pid, stats in cent.items()]
        players.sort(key=lambda x: x.get('hub_score', 0), reverse=True)
        
        return {'team_id': team_id, 'n_games_analyzed': n_games, 'players': players}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
