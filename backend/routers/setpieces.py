# 세트피스 분석 API 라우터
from fastapi import APIRouter, HTTPException
from services.core.data import team_events, data_mark
from services.analyzers.setpiece import team_list, set_box, SetPieceAnalyzer

# 라우트 엔드포인트를 묶어줄 FastAPI 라우터 객체 할당
router = APIRouter()

# 팀 세트피스 루틴 분석
@router.get("/{team_id}")
def setpieces(team_id: int, n_games: int = 5, n_top: int = 2):
    try:
        # 캐시 키용 스탬프 확보 후 캐싱된 set_box 진입점으로 위임 (note_box와 캐시 공유)
        mark = data_mark()
        routines = set_box(team_id, n_games, n_top, mark)
        if not routines:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")

        # 코너킥/프리킥 총 발생 횟수는 별도 카운팅 (원본 이벤트 필터링)
        events = team_events(team_id, n_games)
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
        # 최근 이벤트 집합 쿼리
        events = team_events(team_id, n_games)
        # 이벤트 없으면 예외 전파
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        # 세트피스 전용 분석기 인스턴스 초기화
        analyzer = SetPieceAnalyzer(events)
        # 전체 세트피스 전술 모음집 리스트 추출
        all_routines = analyzer.routine_list()
        # 리스트 내 이벤트 타입에 Corner 글자가 포함된 루틴만 필터링하여 코너킥 전용 배열 생성
        corners = [r for r in all_routines if 'Corner' in r['type']]
        
        # 코너킥 데이터가 1건도 없다면 빈 배열과 함께 조기 종료
        if not corners:
            return {'team_id': team_id, 'message': '코너킥 데이터 없음', 'corners': []}
        
        # 필터링된 코너킥 배열을 순회하며 각종 누적 스탯 집계 딕셔너리 초기화
        stats = {
            'total': len(corners), # 총 코너킥 시도 횟수
            'with_shot': len([c for c in corners if c['has_shot']]), # 코너킥 이후 유효한 슈팅까지 이어진 횟수
            'with_goal': len([c for c in corners if c['has_goal']]), # 코너킥 전개가 실제 골 득점으로 이어진 횟수
            'inswing': len([c for c in corners if c.get('swing_type') == 'inswing']), # 안쪽으로 말려 들어오는 인스윙 궤적 킥 횟수
            'outswing': len([c for c in corners if c.get('swing_type') == 'outswing']) # 바깥으로 휘핑되는 아웃스윙 궤적 킥 횟수
        }
        # 전체 시도 대비 Shot Rate을 소수점 셋째 자리까지 계산
        stats['shot_rate'] = round(stats['with_shot'] / stats['total'], 3) if stats['total'] > 0 else 0
        
        # 코너킥 크로스가 첫 번째로 향한 타겟 구역 빈도수 집계용 딕셔너리
        zones = {}
        # 분류된 코너킥 건들을 1개씩 순회
        for c in corners:
            # 1차 타겟 포지션 구역 명칭 추출
            zone = c.get('first_target_zone', 'unknown')
            # 딕셔너리 키 기반 카운팅 + 1 누적
            zones[zone] = zones.get(zone, 0) + 1
        
        # 소속 팀, 시도 횟수 기반 집산 통계, 타겟 구역 빈도수 종합본 릴리즈
        return {'team_id': team_id, 'n_games_analyzed': n_games, 'stats': stats, 'target_zones': zones}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 프리킥 상세 분석
@router.get("/{team_id}/freekicks")
def freekicks(team_id: int, n_games: int = 5):
    try:
        # 최근 이벤트 집합 쿼리
        events = team_events(team_id, n_games)
        # 이벤트 없으면 예외 전파
        if len(events) == 0:
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        # 세트피스 분석망 가동
        analyzer = SetPieceAnalyzer(events)
        # 전체 세트피스 건수 배열 확보
        all_routines = analyzer.routine_list()
        # 타입 명칭 문자열 안에 'Freekick' 대분류가 포함된 루틴만 골라 프리킥 전용 배열 구성
        freekicks = [r for r in all_routines if 'Freekick' in r['type']]
        
        # 성립된 프리킥이 하나도 없으면 메시지와 함께 빈 객체 조기 반환
        if not freekicks:
            return {'team_id': team_id, 'message': '프리킥 데이터 없음', 'freekicks': []}
        
        # 코너킥과 유사한 포맷으로 총 시도량 및 슈팅/득점 성공량 집계 딕셔너리 빌드
        stats = {
            # 측정된 총 프리킥 발생 수량
            'total': len(freekicks),
            # 연계 플레이든 직접 킥이든 슈팅으로 귀결된 케이스 수
            'with_shot': len([f for f in freekicks if f['has_shot']]),
            # 프리킥 루틴 안에서 득점을 만들어낸 케이스 수
            'with_goal': len([f for f in freekicks if f['has_goal']])
        }
        # 총 프리킥 기회 대비 슈팅 비율 연산 (분모 0 레퍼런스 방어 처리)
        stats['shot_rate'] = round(stats['with_shot'] / stats['total'], 3) if stats['total'] > 0 else 0
        
        # 파울을 획득하여 프리킥이 진행된 필드 시작 위치(X 좌표 깊이 기준) 분포 초기화
        positions = {'attacking': 0, 'midfield': 0, 'defensive': 0}
        # 모아진 프리킥 리스트 순회 탐색
        for f in freekicks:
            # 베이스 시작 X 좌표 획득 (누락시 0 셋)
            x = f.get('start_x', 0)
            # 공격 파이널 서드 구역 (X 75 이상 깊은 지역) 프리킥이면 공격 진영 가산
            if x > 75: positions['attacking'] += 1
            # 미드 1/3 구역 (X 35 ~ 75 사이 하프라인 주변) 이면 미들 진영 가산
            elif x > 35: positions['midfield'] += 1
            # 우리편 수비 지역 (X 35 미만 후방) 이면 수비 진영 가산
            else: positions['defensive'] += 1
        
        # 팀 ID와 함께 조립된 프리킥 퀄리티 및 위치 분포 통계 서빙
        return {'team_id': team_id, 'n_games_analyzed': n_games, 'stats': stats, 'positions': positions}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
