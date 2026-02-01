# 세트피스 분석 API 라우터
from fastapi import APIRouter, HTTPException

from services.core.data import team_events
from services.analyzers.setpiece import team_list, SetPieceAnalyzer

router = APIRouter()


# 팀 세트피스 루틴 분석
@router.get("/{team_id}")
def setpieces(team_id: int, n_games: int = 5, n_top: int = 2):
    try:
        events = team_events(team_id, n_games)
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        routines = team_list(events, n_top)
        setpiece_counts = {
            'corners': len(events[events['type_name'] == 'Pass_Corner']),
            'freekicks': len(events[events['type_name'].str.contains('Freekick', na=False)])
        }
        
        return {'team_id': team_id, 'n_games_analyzed': n_games, 
                'setpiece_counts': setpiece_counts, 'routines': routines}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 코너킥 상세 분석
@router.get("/{team_id}/corners")
def corners(team_id: int, n_games: int = 5):
    try:
        events = team_events(team_id, n_games)
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        analyzer = SetPieceAnalyzer(events)
        all_routines = analyzer.routine_list()
        corners = [r for r in all_routines if 'Corner' in r['type']]
        
        if not corners:
            return {'team_id': team_id, 'message': '코너킥 데이터 없음', 'corners': []}
        
        stats = {
            'total': len(corners),
            'with_shot': len([c for c in corners if c['has_shot']]),
            'with_goal': len([c for c in corners if c['has_goal']]),
            'inswing': len([c for c in corners if c.get('swing_type') == 'inswing']),
            'outswing': len([c for c in corners if c.get('swing_type') == 'outswing'])
        }
        stats['shot_rate'] = round(stats['with_shot'] / stats['total'], 3) if stats['total'] > 0 else 0
        
        zones = {}
        for c in corners:
            zone = c.get('first_target_zone', 'unknown')
            zones[zone] = zones.get(zone, 0) + 1
        
        return {'team_id': team_id, 'n_games_analyzed': n_games, 'stats': stats, 'target_zones': zones}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 프리킥 상세 분석
@router.get("/{team_id}/freekicks")
def freekicks(team_id: int, n_games: int = 5):
    try:
        events = team_events(team_id, n_games)
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        analyzer = SetPieceAnalyzer(events)
        all_routines = analyzer.routine_list()
        freekicks = [r for r in all_routines if 'Freekick' in r['type']]
        
        if not freekicks:
            return {'team_id': team_id, 'message': '프리킥 데이터 없음', 'freekicks': []}
        
        stats = {
            'total': len(freekicks),
            'with_shot': len([f for f in freekicks if f['has_shot']]),
            'with_goal': len([f for f in freekicks if f['has_goal']])
        }
        stats['shot_rate'] = round(stats['with_shot'] / stats['total'], 3) if stats['total'] > 0 else 0
        
        positions = {'attacking': 0, 'midfield': 0, 'defensive': 0}
        for f in freekicks:
            x = f.get('start_x', 0)
            if x > 75: positions['attacking'] += 1
            elif x > 35: positions['midfield'] += 1
            else: positions['defensive'] += 1
        
        return {'team_id': team_id, 'n_games_analyzed': n_games, 'stats': stats, 'positions': positions}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
