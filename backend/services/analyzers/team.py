# 팀 강약점 AI 분석 서비스
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from ..core.cache import layered_cache
from ..core.data import match_events, team_events
from .pattern import team_pat, pat_box
from .setpiece import team_list, set_box
from .network import net_box
from ..core.spec import Analyzer

# 여러 서브 분석기(패턴, 세트피스, 허브)의 결과 JSON을 종합 분석해 팀 강/약점 텍스트 리스트를 뽑아내는 함수
def team_stats(team_id: int, patterns: List[Dict], setpieces: List[Dict], hubs: List[Dict]) -> Dict:
    # 강점 리스트 초기화
    strengths = []
    # 약점 리스트 초기화
    weaknesses = []
    # 핵심 인사이트 요약 리스트 초기화
    insights = []
    
    # 공격 패턴 분석 데이터가 존재한다면 평가 시작
    if patterns:
        # 각 패턴들의 슈팅 전환율 정보만 뽑아내어 평균값 산출
        avg_shot_rate = np.mean([p.get('shot_conversion_rate', 0) for p in patterns])
        # 가장 전환율(파괴력)이 높았던 패턴의 최고 수치 스캔
        max_shot_rate = max([p.get('shot_conversion_rate', 0) for p in patterns])
        # 모든 공격 패턴이 시도된 총 횟수(볼륨) 집계
        total_frequency = sum([p.get('frequency', 0) for p in patterns])

        # 유의미한 표본 횟수(30번 이상)의 패턴 누적이 있고
        if total_frequency >= 30:
            # 베스트 패턴의 슈팅 창출 확률이 18%가 넘을 정도로 파괴력이 입증됐다면
            if max_shot_rate > 0.18:
                # 이걸 팀의 '강점' 항목으로 분류하여 저장
                strengths.append({'category': '공격', 'title': '높은 슈팅 전환율',
                    'description': f'최고 {max_shot_rate*100:.0f}% 전환율의 위험한 공격 패턴 보유',
                    'score': min(100, int(max_shot_rate * 400))})
            # 반대로 어떤 패턴을 쓰든 최대치 슈팅 창출 확률이 8%도 안된다면
            elif max_shot_rate < 0.08:
                # 팀의 '약점' 항목(무딘 공격 체계)으로 분류하여 저장
                weaknesses.append({'category': '공격', 'title': '낮은 결정력',
                    'description': f'공격 패턴의 슈팅 전환율이 {max_shot_rate*100:.0f}%로 저조',
                    'score': max(20, int(max_shot_rate * 400))})

        # 공격 시도 빈도(볼륨) 자체가 250회가 넘을 정도로 왕성한 편이라면
        if total_frequency > 250:
            strengths.append({'category': '공격', 'title': '다양한 공격 루트',
                'description': f'{total_frequency}회의 다채로운 공격 시도',
                'score': min(100, int(total_frequency / 5))})
        # 반대로 총 묶인 시도 패턴 건수가 80회도 안될 정도로 빈약하다면
        elif total_frequency < 80:
            weaknesses.append({'category': '공격', 'title': '공격 전개 부족',
                'description': f'최근 패턴 빈도가 {total_frequency}회로 낮음',
                'score': 45})
    
    # 세트피스 분석 데이터가 존재하면 평가 개시
    if setpieces:
        # 코너킥 루틴만 별도로 필터링
        corner_routines = [s for s in setpieces if 'Corner' in s.get('type', '')]
        # 프리킥 루틴만 별도로 필터링
        freekick_routines = [s for s in setpieces if 'Freekick' in s.get('type', '')]
        
        # 코너킥 루틴이 존재한다면
        if corner_routines:
            # 횟수 누합
            corner_total = sum([c.get('frequency', 0) for c in corner_routines])
            # 루틴 발생 빈도를 가중치(Weights)로 둔 가중 평균 코너킥 슈팅 효율값 연산
            avg_corner_rate = np.average(
                [c.get('shot_rate', 0) for c in corner_routines],
                weights=[max(c.get('frequency', 0), 1) for c in corner_routines],
            )
            # 표본 8회 이상 만족 시
            if corner_total >= 8:
                # 코너킥 슈팅 연결 확률 28% 초과면 강점으로 기록
                if avg_corner_rate > 0.28:
                    strengths.append({'category': '세트피스', 'title': '코너킥 위협',
                        'description': f'코너킥에서 {avg_corner_rate*100:.0f}% 슈팅 전환',
                        'score': min(100, int(avg_corner_rate * 220))})
                # 코너킥 찼다 하면 슈팅 확률 12% 이하면 약점으로 기록
                elif avg_corner_rate < 0.12:
                    weaknesses.append({'category': '세트피스', 'title': '코너킥 효율 저조',
                        'description': f'코너킥 슈팅 전환율 {avg_corner_rate*100:.0f}%로 개선 필요',
                        'score': max(20, int(avg_corner_rate * 220))})
        
        # 프리킥 루틴 평가
        if freekick_routines:
            fk_total = sum([f.get('frequency', 0) for f in freekick_routines])
            # 프리킥 발생 건수 비중별 슈팅 효율 가중평균
            avg_fk_rate = np.average(
                [f.get('shot_rate', 0) for f in freekick_routines],
                weights=[max(f.get('frequency', 0), 1) for f in freekick_routines],
            )
            # 표본 6회 이상
            if fk_total >= 6:
                # 무려 프리킥의 22% 이상이 슈팅 귀결 시 스페셜리스트 강점
                if avg_fk_rate > 0.22:
                    strengths.append({'category': '세트피스', 'title': '프리킥 전문가',
                        'description': f'프리킥에서 {avg_fk_rate*100:.0f}% 슈팅 전환',
                        'score': min(100, int(avg_fk_rate * 220))})
                # 프리킥 효율 10% 미만 시 약점으로 기록
                elif avg_fk_rate < 0.1:
                    weaknesses.append({'category': '세트피스', 'title': '프리킥 활용 저조',
                        'description': f'프리킥 슈팅 전환율 {avg_fk_rate*100:.0f}%로 개선 필요',
                        'score': 40})
    
    # 패스 네트워크(빌드업 허브) 분석 결과 처리
    if hubs:
        # 가장 영향력이 막강한 1등 허브 선수 추출
        top_hub = hubs[0] if hubs else None
        if top_hub:
            # 1등 선수의 영향력 점수 및 누적 패스 수
            hub_score = top_hub.get('hub_score', 0)
            passes_made = top_hub.get('passes_made', 0)
            
            # 허브스코어가 0.8(80%)를 넘길 정도로 경기를 쥐락펴락한다면 에이스 특성 기록
            if hub_score > 0.8:
                strengths.append({'category': '빌드업', 'title': '핵심 플레이메이커',
                    'description': f"{top_hub.get('player_name', '선수')}가 공격 조율의 핵심",
                    'score': min(100, int(hub_score * 100))})
            
            # 단일 선수가 최근 5경기에 400번 넘는 패스를 꼬박 뿌렸다면 볼 순환 강점 인정
            if passes_made > 400:
                strengths.append({'category': '빌드업', 'title': '안정적 볼 순환',
                    'description': f'핵심 허브가 {passes_made}회 패스로 경기 지배',
                    'score': min(100, int(passes_made / 5))})
        
        # 허브 데이터가 2명 이상 뽑혀 있을 때, 원맨팀 여부 판별
        if len(hubs) >= 2:
            hub_scores = [h.get('hub_score', 0) for h in hubs[:3]]
            # 1등 선수의 영향력이 2등 선수보다 1.5배 이상 막강하다면 '지나친 원맨 집중 현상' 약점 기록
            if hub_scores[0] > hub_scores[1] * 1.5:
                weaknesses.append({'category': '빌드업', 'title': '허브 의존도 높음',
                    'description': f"1번 허브 {hubs[0].get('player_name', '')}에 과도하게 의존",
                    'score': 45})
    
    # 복합 교차 추가 약점 로직 필터링
    if patterns:
        # 전체 뚜렷한 대표 패턴이 3가지 이하밖에 없는 단조로운 팀일 때 기록
        if len(patterns) < 4:
            weaknesses.append({'category': '공격', 'title': '패턴 다양성 부족',
                'description': f'{len(patterns)}개의 한정된 공격 루트만 보유', 'score': 50})
        
        # 공격이 전개되는 템포(지연 시간)가 평균 40초를 넘길 만큼 지공(답답함) 성향이면 타격 기록
        avg_duration = np.mean([p.get('avg_duration', 0) for p in patterns])
        if avg_duration > 40:
            weaknesses.append({'category': '공격', 'title': '느린 빌드업 템포',
                'description': f'평균 {avg_duration:.0f}초의 긴 빌드업, 역습에 취약 가능', 'score': 55})
    
    # 특정 선수에게로 가는 패스 몰빵(루트 다채로움 부족) 분석
    if hubs and len(hubs) >= 2:
        receives = [h.get('passes_received', 0) for h in hubs[:2]]
        # 1등 허브와 2등 허브가 받은 패스 양의 비율
        if receives[0] > 0 and receives[1] > 0:
            ratio = receives[0] / max(receives[1], 1)
            # 특정 1명 한테만 1.8배 이상 패스가 몰린다면, 그 선수만 담그면 경기가 망가지므로 약점 처리
            if ratio > 1.8:
                weaknesses.append({'category': '빌드업', 'title': '패스 루트 예측 가능',
                    'description': '특정 선수로의 패스 집중, 상대 압박에 취약', 'score': 50})
    
    # 스카우팅 리포트 상단에 들어갈 짧고 강렬한 이모지 1줄 한줄평(Insights) 조립
    if strengths:
        # 스코어 기준 가장 강력한 무기 추출
        top_strength = max(strengths, key=lambda x: x['score'])
        insights.append(f"💪 가장 큰 강점: {top_strength['title']}")
    if weaknesses:
        # 스코어 기준 가장 치명적인 결점 추출 (역산)
        top_weakness = max(weaknesses, key=lambda x: 100 - x['score'])
        insights.append(f"⚠️ 개선 필요: {top_weakness['title']}")
    # 다양성 정보 추가
    if patterns and len(patterns) >= 3:
        insights.append(f"📊 {len(patterns)}개의 주요 공격 패턴 보유")
    if setpieces:
        insights.append(f"⚽ {len(setpieces)}개의 세트피스 루틴 분석됨")
    
    # 0~100 환산 스케일로 팀 전체 오버롤 점수화 (레이더 차트용 등)
    all_scores = [s['score'] for s in strengths] + [w['score'] for w in weaknesses]
    overall_score = int(np.mean(all_scores)) if all_scores else 50
    
    # 분석 레포트 JSON 덩어리로 직렬화하여 반환
    return {
        'team_id': team_id,
        'overall_score': overall_score,
        # 강점 상위 3개만 나열
        'strengths': sorted(strengths, key=lambda x: x['score'], reverse=True)[:3],
        # 약점 상위 3개만 나열 (수치가 높을수록 덜 치명적이라는 로직이면 오름차순)
        'weaknesses': sorted(weaknesses, key=lambda x: x['score'])[:3],
        # 인사이트 최대 4줄
        'insights': insights[:4],
        # 서면 요약 코멘트 추가 생성
        'summary': sum_text(strengths, weaknesses)
    }


# 강점 및 약점 분류(Category) 명칭들을 이어붙여 자연스러운 한글 한 줄 평가 문장을 만들어주는 헬퍼
def sum_text(strengths: List[Dict], weaknesses: List[Dict]) -> str:
    # 데이터가 아예 없다면 기본 문자열 반환
    if not strengths and not weaknesses:
        return "분석할 데이터가 부족합니다."
    
    parts = []
    # 강점이 발견된 모든 카테고리 종류(공격, 빌드업 등)를 중복 제거(Set)하여 텍스트 포장
    if strengths:
        strength_cats = list(set([s['category'] for s in strengths]))
        parts.append(f"{', '.join(strength_cats)} 분야에서 강점을 보입니다")
    # 약점이 발견된 분야들 역시 포장
    if weaknesses:
        weak_cats = list(set([w['category'] for w in weaknesses]))
        parts.append(f"{', '.join(weak_cats)} 분야는 개선이 필요합니다")
    
    # 두 문장을 자연스럽게 연결
    return ". ".join(parts) + "."


# 팀 스탯 분석을 매번 생 쿼리 대신 캐싱해놓기 위한 Analyzer 클래스 인터페이스 래퍼
class TeamAnalyzer(Analyzer):
    def __init__(self, team_id: int, n_games: int, mark: tuple):
        self.team_id = team_id
        self.n_games = n_games
        # 데이터베이스 최종 반영된 타임스탬프 (이 값이 바뀌면 캐시가 만료됨을 의미)
        self.mark = mark

    # 패턴/세트피스/허브 세 하위 분석을 병렬 실행하여 병목 완화. 라우터와 캐시 키를 공유함
    def data(self) -> Dict:
        with ThreadPoolExecutor(max_workers=3) as ex:
            pat_fut = ex.submit(pat_box, self.team_id, self.n_games, 5, self.mark)
            set_fut = ex.submit(set_box, self.team_id, self.n_games, 4, self.mark)
            hub_fut = ex.submit(net_box, self.team_id, self.n_games, 3, self.mark)
            patterns = pat_fut.result()
            setpieces = set_fut.result()
            hubs_result = hub_fut.result()

        if not patterns and not setpieces:
            return {}

        hubs = hubs_result.get("hubs", []) if isinstance(hubs_result, dict) else hubs_result
        return team_stats(self.team_id, patterns, setpieces, hubs)


# 라우터에서 빈번히 호출되는 종합 분석 결과를 L1(메모리) + L2(DiskCache) 2단 캐시로 메모이즈
# TeamAnalyzer 내부는 pat_box(.., 5) / set_box(.., 4) / net_box(.., 3) 호출 — 라우터 기본값과 top_k가 달라 별도 키 (warmup이 양쪽 prewarm)
@layered_cache("note", maxsize=256)
def note_box(team_id: int, n_games: int, mark: tuple) -> Dict:
    analyzer = TeamAnalyzer(team_id, n_games, mark)
    return analyzer.data()
