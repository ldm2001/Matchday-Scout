# 네트워크 분석 API 라우터
from fastapi import APIRouter, HTTPException
from services.core.data import team_events, data_mark
from services.analyzers.network import net_box, NetworkAnalyzer

# 네임스페이스 분리를 위한 FastAPI 라우터 객체 할당
router = APIRouter()

# 특정 팀의 경기 패스 데이터를 기반으로 허브 플레이어 정보를 분석
@router.get("/{team_id}")
def network(team_id: int, n_games: int = 5, n_hubs: int = 2):
    try:
        # 데이터가 마지막으로 업데이트된 기준 시간 확인
        mark = data_mark()
        # net_box를 호출하여 네트워크 분석 결과 획득
        result = net_box(team_id, n_games, n_hubs, mark)
        # 조회된 이벤트 분석 데이터가 없으면 404 리턴
        if not result:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
            
        # 프론트엔드 소비를 위해 분석 결과 JSON 구조 포매팅 후 반환
        return {
            # 조회 대상 팀 ID
            'team_id': team_id,
            # 분석에 활용된 표본 경기 수
            'n_games_analyzed': n_games,
            # 식별된 주요 허브 선수 목록 추출
            'hubs': result.get('hubs', []),
            # 네트워크 그래프의 노드(선수) 및 엣지(패스 연결) 개수 메타데이터 전송
            'network_stats': {
                'nodes': len(result.get('network', {}).get('nodes', [])),
                'edges': len(result.get('network', {}).get('edges', []))
            }
        }
    except HTTPException:
        # 직접 발생시킨 404 예외 등은 터치 없이 그대로 상위 전달
        raise
    except Exception as e:
        # 알 수 없는 런타임 오류는 500 상태 코드로 래핑
        raise HTTPException(status_code=500, detail=str(e))

# 시각화용 네트워크 그래프 데이터
@router.get("/{team_id}/graph")
def graph(team_id: int, n_games: int = 5):
    try:
        # DB 변경 상태 체크를 위한 최신 스탬프 조회
        mark = data_mark()
        # 캐싱 로직을 통과하여 네트워크 그래프 전체 분석본 산출
        result = net_box(team_id, n_games, 2, mark)
        # 경기 데이터가 전혀 존재하지 않으면 404 예외 처리
        if not result:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        # network 필드 안에 담긴 상세 구조만 전달
        return {
            'team_id': team_id,
            'n_games_analyzed': n_games,
            # 만약 속성이 비어있다면 빈 배열 기본값 헬퍼 사용
            'graph': result.get('network', {'nodes': [], 'edges': []})
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 특정 허브 선수 상세 정보
# 분석된 네트워크 망에서 특정 선수 1명에 대해 연결성 및 대체 불가성(Impact)을 집중 심층 조회하는 API
@router.get("/{team_id}/hubs/{player_id}")
def hub_detail(team_id: int, player_id: int, n_games: int = 5):
    try:
        # 코어 DB에서 해당 팀의 최근 경기 이벤트 로우데이터를 있는 그대로 긁어옴
        events = team_events(team_id, n_games)
        # 패스 맵을 그릴 재료가 없으면 404 로 튕겨냄
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        # 수동으로 NetworkAnalyzer 인스턴스를 생성하여 실시간 분석 준비
        analyzer = NetworkAnalyzer(events)
        # 내부 구조체에 선수 노드와 패스 엣지 네트워크 망 빌드
        analyzer.net_graph()
        # PageRank나 Betweenness 기준 등을 혼합하여 선수별 관여도 중심성 지표 계산
        cent = analyzer.cent()
        
        # 요청된 선수 ID가 계산된 맵 안에 없다면 에러 (해당 경기들에서 뛰지 않았거나 터치가 0인 경우)
        if player_id not in cent:
            raise HTTPException(status_code=404, detail="해당 선수를 찾을 수 없습니다")
        
        # 특정 선수에 대응하는 중심성 스탯 통계 추출
        stats = cent[player_id]
        
        # 선수의 연결 가치 및 연결망 손실 임팩트 지수를 상세 반환
        return {
            'team_id': team_id, 'player_id': player_id,
            'player_name': stats['name'], # 선수 이름 텍스트
            'position': stats['position'], # 포메이션상 주 구역 포지션
            'stats': stats, # 각종 센트럴리티 정보
            'key_connections': analyzer.link_list(player_id, 5), # 해당 선수와 가장 패스를 많이 주고받은 주요 커넥션 대상 상위 5인 리스트
            'disruption_impact': analyzer.impact_stat(player_id) # 이 선수가 결장할 경우 팀 패스망 붕괴 위험도 시뮬레이션 영향 스탯
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 모든 선수의 중심성 지표
@router.get("/{team_id}/centrality")
def cent_data(team_id: int, n_games: int = 5):
    try:
        # 파라미터 기반 최근 이벤트 원시 집합 쿼리
        events = team_events(team_id, n_games)
        # 이벤트가 없으면 로직을 조기 종료시켜 불필요한 연산 방지
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        # 실시간 네트워크 객체 초기화
        analyzer = NetworkAnalyzer(events)
        # 그래프 트리 연산 수행
        analyzer.net_graph()
        # 선수별 중심성(허브 점수) 전체 도출
        cent = analyzer.cent()
        
        # 딕셔너리 포맷을 프론트가 읽기 편한 평면(Flat) 리스트 객체 형태로 변환 시작
        # JSON 직렬화를 위해 ID 타입 캐스팅 진행 및 파이썬 Unpacking 문법 결합
        players = [{'player_id': int(pid) if not isinstance(pid, str) else pid, **stats}
                   for pid, stats in cent.items()]
                   
        # 배열을 가장 허브 스코어가 높은 선수부터 1등으로 오게끔(Reverse) 내림차순 정렬
        players.sort(key=lambda x: x.get('hub_score', 0), reverse=True)
        
        # 정렬된 선수들의 네트워크 영향력 순위표를 최종 반환
        return {'team_id': team_id, 'n_games_analyzed': n_games, 'players': players}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
