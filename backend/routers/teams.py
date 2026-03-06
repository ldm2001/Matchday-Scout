# 팀 관련 API 라우터
from fastapi import APIRouter, HTTPException
from typing import Optional
from services.core.data import teams as team_rows, team_events, matches as match_rows
router = APIRouter()

# K리그 팀 목록 조회
@router.get("/")
def teams():
    try:
        # 데이터 서비스 계층에서 전체 팀 정보 리스트 패치
        team_list = team_rows()
        # 데이터와 총 팀 개수를 묶어 JSON 응답 반환
        return {"teams": team_list, "count": len(team_list)}
    except Exception as e:
        # DB 에러 등 런타임 문제 발생 시 500 인터널 서버 에러 발생
        raise HTTPException(status_code=500, detail=str(e))

# 전체 팀 성적 개요
@router.get("/overview")
def overview():
    try:
        # 전체 경기 기록 데이터 프레임 조회
        match_df = match_rows()
        # 전체 팀 정보 배열 조회
        team_list = team_rows()
        # 최종 순위표 데이터를 담을 배열 초기화
        standings = []
        
        # 각 팀별 스탯을 순회하며 개별 집계 시작
        for team in team_list:
            # 베이스 기록이 될 팀 고유 ID 추출
            team_id = team['team_id']
            # 프론트 표시용 팀 이름 필드 추출
            team_name = team['team_name']
            
            # 해당 팀이 홈 자격으로 치른 메인 경기 결과만 필터링
            home_matches = match_df[match_df['home_team_id'] == team_id]
            # 해당 팀이 원정 자격으로 치른 어웨이 경기 결과만 필터링
            away_matches = match_df[match_df['away_team_id'] == team_id]
            
            # 누적 승, 무, 패 스탯 변수 초기 세팅
            wins, draws, losses = 0, 0, 0
            # 총 득점량, 실점량 스탯 변수 0 세팅
            goals_for, goals_against = 0, 0
            
            # 필터링된 홈 경기 결과 순회
            for _, m in home_matches.iterrows():
                # 내가 홈이므로 홈 스코어를 내 득점으로 가산
                goals_for += m['home_score']
                # 어웨이 스코어는 나의 실점으로 가산
                goals_against += m['away_score']
                # 득점이 많으면 승리 카운트 쁠러스
                if m['home_score'] > m['away_score']: wins += 1
                # 동점이면 무승부 카운트 쁠러스
                elif m['home_score'] == m['away_score']: draws += 1
                # 득점이 적으면 패배 카운트 쁠러스
                else: losses += 1
            
            # 필터링된 원정 경기 결과 순회
            for _, m in away_matches.iterrows():
                # 내가 원정이므로 어웨이 스코어를 내 득점으로 가산
                goals_for += m['away_score']
                # 홈 스코어는 나의 실점으로 가산
                goals_against += m['home_score']
                # 역으로 판정하여 승무패 카운트 적용
                if m['away_score'] > m['home_score']: wins += 1
                elif m['away_score'] == m['home_score']: draws += 1
                else: losses += 1
            
            # 홈 원정 합산 누적 경기수(Played) 계산
            total_matches = len(home_matches) + len(away_matches)
            # 승점 계산 공식(승 3점, 무 1점) 적용
            points = wins * 3 + draws
            
            # 분위기(Form) 파악을 위한 홈/어웨이 상관 없는 팀 경기 전체 합산 내역 쿼리
            all_matches = match_df[
                (match_df['home_team_id'] == team_id) | (match_df['away_team_id'] == team_id)
            # 최신 경기부터 역순으로 정렬한 뒤 가장 최근 5경기만(Head) 추출
            ].sort_values('game_date', ascending=False).head(5)
            
            # 5경기의 W/D/L 결과 기록을 나열할 배열 변수
            form = []
            # 최신 5경기를 1건씩 순회
            for _, m in all_matches.iterrows():
                # 이번 경기가 나의 홈 구장이었는지 식별
                is_home = m['home_team_id'] == team_id
                # 홈 구장이었다면
                if is_home:
                    # 홈 스코어가 높으면 승리(W) 추가
                    if m['home_score'] > m['away_score']: form.append('W')
                    # 같으면 무승부(D)
                    elif m['home_score'] == m['away_score']: form.append('D')
                    # 낮으면 패배(L) 처리
                    else: form.append('L')
                # 원정이었다면
                else:
                    # 기준 반전하여 승무패 기록 판단 후 배열에 축적
                    if m['away_score'] > m['home_score']: form.append('W')
                    elif m['away_score'] == m['home_score']: form.append('D')
                    else: form.append('L')
            
            # 순위표에 들어갈 한 줄 단위 팀 성적 종합 요약 객체 완성
            standings.append({
                'team_id': team_id, 'team_name': team_name, 'played': total_matches,
                'wins': wins, 'draws': draws, 'losses': losses,
                'goals_for': int(goals_for), 'goals_against': int(goals_against),
                'goal_diff': int(goals_for - goals_against), 'points': points, 'form': form
            })
        
        # 반복문 종료 후 순위표를 [승점 높은순 -> 골득실 높은순 -> 다득점 높은순]으로 다중 조건 정렬 내림차순 정렬
        standings.sort(key=lambda x: (-x['points'], -x['goal_diff'], -x['goals_for']))
        # 정렬된 순위표 배열을 순회하며 1위부터 순차적으로 Rank 넘버 매기기
        for i, team in enumerate(standings):
            team['rank'] = i + 1
        
        # 가공 완료된 순위표 배열과 총 팀 수를 JSON 응답으로 반환
        return {"standings": standings, "total_teams": len(standings)}
    except Exception as e:
        # DB 에러 등 런타임 문제 발생 시 500 인터널 서버 에러 발생
        raise HTTPException(status_code=500, detail=str(e))


# URL 라우트에 기입된 특정 팀 고유 ID를 기반으로 상세 정보를 조회하는 API
@router.get("/{team_id}")
def info(team_id: int):
    try:
        # 전체 경기 기록 데이터 프레임 쿼리
        match_df = match_rows()
        # 질의된 팀 ID가 홈 팀이었던 경기 결과만 필터링
        home_matches = match_df[match_df['home_team_id'] == team_id]
        # 질의된 팀 ID가 원정 팀이었던 경기 결과만 필터링
        away_matches = match_df[match_df['away_team_id'] == team_id]
        
        # 홈에서도 원정에서도 치른 경기가 하나도 없다면 존재하지 않는 팀으로 간주
        if len(home_matches) == 0 and len(away_matches) == 0:
            # 404 Not Found HTTP 예외 발생
            raise HTTPException(status_code=404, detail="팀을 찾을 수 없습니다")
        
        # 홈 경기 기록이 있다면 홈 팀명, 없다면 어웨이 팀명 컬럼을 참조하여 팀 한글명 추출
        team_name = home_matches.iloc[0]['home_team_name_ko'] if len(home_matches) > 0 else away_matches.iloc[0]['away_team_name_ko']
        # 전체 치른 경기 수 집산
        total_matches = len(home_matches) + len(away_matches)
        
        # 해당 팀이 참여한 모든 경기를 날짜 최신순으로 정렬한 데이터 프레임 생성
        all_matches = match_df[
            (match_df['home_team_id'] == team_id) | (match_df['away_team_id'] == team_id)
        ].sort_values('game_date', ascending=False)
        
        # 가장 최근 치른 5경기의 요약 기록을 담을 배열 변수 선언
        recent_matches = []
        # 최신 5개 경기 데이터 프레임 순회
        for _, m in all_matches.head(5).iterrows():
            # 조회된 팀의 홈 경기인지 판별 플래그
            is_home = m['home_team_id'] == team_id
            # 최근 경기 목록에 핵심 정보만 추려서 객체로 추가
            recent_matches.append({
                # 대상 경기 고유 ID
                'game_id': int(m['game_id']),
                # 경기가 치뤄진 날짜 포맷
                'date': str(m['game_date']),
                # 내 기준 상대 팀 이름 노출 처리
                'opponent': m['away_team_name_ko'] if is_home else m['home_team_name_ko'],
                # 홈(H)인지 어웨이(A)인지 구분자 알파벳
                'venue': 'H' if is_home else 'A',
                # 홈 대 어웨이 형식의 스코어 보드 문자 포매팅
                'score': f"{m['home_score']}-{m['away_score']}"
            })
        
        # 조회된 팀의 메타 데이터와 최신 5경기 요약 내역을 묶어서 JSON 반환
        return {'team_id': team_id, 'team_name': team_name, 'total_matches': total_matches, 'recent_matches': recent_matches}
    except HTTPException:
        # HTTPException은 의도된 에러이므로 그대로 위로 패스
        raise
    except Exception as e:
        # 기타 런타임 에러는 500 에러로 래핑하여 리턴
        raise HTTPException(status_code=500, detail=str(e))


# 특정 팀이 참여한 최근 N경기 동안의 주요 발생 이벤트들을 요약 집계하는 API
@router.get("/{team_id}/events")
def events(team_id: int, n_games: int = 5):
    try:
        # 코어 데이터 서비스에서 해당 팀의 최근 N경기치 이벤트 목록 쿼리
        events = team_events(team_id, n_games)
        # 이벤트가 단 1건도 돌아오지 않았다면 (경기 기록 부재 등)
        if len(events) == 0:
            # 404 응답 코드와 함께 예외 쓰로우
            raise HTTPException(status_code=404, detail="이벤트 데이터가 없습니다")
        
        # 발생한 이벤트들의 종류(패스, 슛 등)별로 카운팅 그룹핑 후 딕셔너리로 변환
        event_stats = events['type_name'].value_counts().to_dict()
        # 이벤트를 발생시킨 주체 선수 단위로 다시 카운팅 그룹핑 수행
        player_stats = events.groupby(['player_id', 'player_name_ko']).size().reset_index(name='event_count')
        # 이벤트 발생 빈도가 가장 높은 상위 10명의 에이스 선수 목록 추출 후 직렬화
        top_players = player_stats.nlargest(10, 'event_count').to_dict('records')
        
        # 팀 아이디, 조회 경기 수, 이벤트 종류별 통계, 핵심 플레이어 목록 종합 리턴
        return {'team_id': team_id, 'n_games': n_games, 'total_events': len(events),
                'event_types': event_stats, 'top_players': top_players}
    except HTTPException:
        # 우리가 의도하여 발생시킨 HTTP 에러 규격은 유지
        raise
    except Exception as e:
        # 스크립트 실행 중 발생한 기타 예외는 500 에러 처리
        raise HTTPException(status_code=500, detail=str(e))
