# 선수들의 연속된 플레이 흐름을 나누는 Phase 분할 및 클러스터링 분석 모듈
from __future__ import annotations
from collections import Counter
from typing import Dict, Iterable, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
from ..core.cache import layered_cache
from ..core.spadl import action_rows, spadl_map
from ..core.spec import Analyzer

# 연속된 이벤트 흐름을 의미있는 부분 전술 시간대(Phase) 단위로 자르는 분석기
class PhaseAnalyzer(Analyzer):
    PHASE_GAP_SECONDS = 10 # 한 국면(Phase)이 끊어지고 새 국면으로 넘어가는 기준 시간 공백
    MIN_PHASE_EVENTS = 3 # 하나의 국면으로 인정받기 위한 최소 연속 액션 발생 횟수

    # 전처리 완료된 이벤트 데이터프레임을 주입받아 초기화
    def __init__(self, events_df: pd.DataFrame):
        # 시간순으로 이벤트를 정렬
        self.events = events_df.sort_values(["game_id", "period_id", "time_seconds", "action_id"])

    # 잘게 잘라낸 국면 데이터프레임들의 리스트를 생성하여 반환
    def phase_list(self) -> List[pd.DataFrame]:
        # 결과물을 담을 빈 리스트 준비
        phases: List[pd.DataFrame] = []

        # 여러 경기가 섞여 있을 수 있으므로 경기(game_id) 단위로 우선 분리 반복
        for game_id in self.events["game_id"].unique():
            # 해당 경기의 이벤트만 추출 후 인덱스 초기화
            game_events = self.events[self.events["game_id"] == game_id].reset_index(drop=True)
            # 텅 빈 경기면 스킵
            if game_events.empty:
                continue

            # 현재 묶여가고 있는 하나의 국면 데이터를 담을 임시 리스트
            current_phase: List[pd.Series] = []
            # 이전 이벤트의 발생 시간 초기화
            prev_time = None
            # 이전 이벤트의 공격 팀 초기화
            prev_team = None
            # 이전 이벤트의 전후반 기준(period_id) 초기화
            prev_period = None

            # 해당 경기의 모든 이벤트를 1개씩 순회
            for _, row in game_events.iterrows():
                # 현재 이벤트의 경과 시간, 소유 팀, 전후반 정보 파싱
                curr_time = row.get("time_seconds", 0)
                curr_team = row.get("team_id", None)
                curr_period = row.get("period_id", None)
                
                # 기본적으론 새로운 페이즈가 시작되지 않았다고 가정
                new_phase = False

                # 첫 번째 이벤트가 아니라 이전 이벤트가 존재한다면 비교 시작
                if prev_time is not None:
                    # 두 이벤트 사이 공백이 설정된 Gap(10초)보다 크면 플레이가 단절되었다고 보고 페이즈를 자름
                    if curr_time - prev_time > self.PHASE_GAP_SECONDS:
                        new_phase = True
                    # 또는 볼 점유 팀이 바뀌어 공수 교대가 일어나면 페이즈를 자름
                    elif prev_team is not None and curr_team is not None and curr_team != prev_team:
                        new_phase = True
                    # 전반 종료 후 후반 시작 등 피어리드가 변했을 경우 페이즈 자름
                    elif prev_period is not None and curr_period is not None and curr_period != prev_period:
                        new_phase = True

                # 잘라야 한다는 신호(new_phase)가 켜졌고, 누적된 과거 액션이 기준 개수 이상이면
                if new_phase and len(current_phase) >= self.MIN_PHASE_EVENTS:
                    # 완성된 페이즈를 데이터프레임화해서 전체 결과 리스트에 편입
                    phases.append(pd.DataFrame(current_phase))
                    # 다음 페이즈를 담기 위해 임시 배열 비움
                    current_phase = []

                # 현재 이벤트를 진행 중인 페이즈 묶음에 추가
                current_phase.append(row)
                # 다음 루프 비교를 위해 이전(prev) 값들을 현재 값으로 갱신
                prev_time = curr_time
                prev_team = curr_team
                prev_period = curr_period

            # 마지막까지 묶인 페이즈가 조건 개수를 채웠다면 잊지 않고 편입
            if len(current_phase) >= self.MIN_PHASE_EVENTS:
                phases.append(pd.DataFrame(current_phase))

        # 경기 전체에서 썰어낸 페이즈 리스트 최종 반환
        return phases

    # Analyzer 스펙 인터페이스 통일용 래퍼 함수
    def data(self) -> List[pd.DataFrame]:
        return self.phase_list()

    # 분리된 단일 페이즈 1개에 대해 기초 통계량을 집계 추출하는 함수
    def phase_stats(self, phase: pd.DataFrame) -> Dict:
        # 비어있으면 빈 딕셔너리 리턴
        if phase.empty:
            return {}

        # 페이즈의 특징값 딕셔너리 빌드 시작
        features = {
            # 몇 개의 액션 기동으로 이루어졌는지 횟수 카운트
            "length": len(phase),
            # 해당 페이즈가 총 몇 초 동안 존속되었는지 시간 차이 계산
            "duration": float(phase["time_seconds"].max() - phase["time_seconds"].min()),
            # 페이즈 시발점 X 좌표 (최초 이벤트 start_x)
            "start_x": float(phase.iloc[0].get("start_x", 0) or 0),
            # 페이즈 시발점 Y 좌표 (최초 이벤트 start_y)
            "start_y": float(phase.iloc[0].get("start_y", 0) or 0),
            # 페이즈 도착점 X 좌표 (최종 이벤트 end_x)
            "end_x": float(phase.iloc[-1].get("end_x", 0) or 0),
            # 페이즈 도착점 Y 좌표 (최종 이벤트 end_y)
            "end_y": float(phase.iloc[-1].get("end_y", 0) or 0),
            # 해당 국면 내 전체 액션들의 출발 x 평균선
            "avg_x": float(phase["start_x"].mean()) if "start_x" in phase.columns else 0.0,
            # 해당 국면 내 전체 액션들의 출발 y 평균선
            "avg_y": float(phase["start_y"].mean()) if "start_y" in phase.columns else 0.0,
            # 썰어간 패스 전개 횟수
            "pass_count": int((phase["type_name"] == "Pass").sum()) if "type_name" in phase.columns else 0,
            # 공을 달고 움직인 전진 드리블/캐리 횟수
            "carry_count": int((phase["type_name"] == "Carry").sum()) if "type_name" in phase.columns else 0,
            # 시도된 슈팅 횟수
            "shot_count": int((phase["type_name"] == "Shot").sum()) if "type_name" in phase.columns else 0,
            # 박스 쪽 크로스 투입 횟수
            "cross_count": int((phase["type_name"] == "Cross").sum()) if "type_name" in phase.columns else 0,
            # X축 방향으로 공을 전진시킨 누적 거리 (dx 기여도)
            "forward_progress": float(phase["dx"].sum()) if "dx" in phase.columns else 0.0,
            # 좌우 횡으로 이동한 궤적 절댓값 누적 거리 (dy 기여도)
            "lateral_movement": float(abs(phase["dy"]).sum()) if "dy" in phase.columns else 0.0,
            # 해당 국면에서 발생한 이벤트들의 문자열 나열을 이어서(A_B_C 형태) 전개 시퀀스 시그니처 텍스트화
            "event_sequence": "_".join(phase["type_name"].tolist()) if "type_name" in phase.columns else "",
        }

        # 성공/실패 여부를 판단할 수 있는 컬럼이 있다면 성공률 스탯도 산출
        if "result_name" in phase.columns:
            # 페이즈 안에서 성공 이벤트와 실패 이벤트를 계수화
            results = phase["result_name"].value_counts()
            # None이 아닌 값이 있는 평가 총합 분모
            total = len(phase[phase["result_name"].notna()])
            # 전체 발생 대비 성공 행동 비율 (실패시 0 처리 파이프라인 안전망)
            features["success_rate"] = results.get("Successful", 0) / total if total > 0 else 0

        # 추출된 특징 딕셔너리 배출
        return features

    # 특정 x, y 물리적 좌표를 받아 논리적인 그라운드 섹터(수비 우측, 공격 박스 등) 텍스트 명칭으로 치환
    def zone_tag(self, x: float, y: float) -> str:
        # X좌표(가로길이 105 기준)상 아군 진영(35 미만), 중앙(35~70), 상대 진영(70 이상) 분류
        x_zone = "수비" if x < 35 else ("중앙" if x < 70 else "공격")
        # Y좌표(세로길이 68 기준)상 좌측(22.6 미만), 중앙(22.6~45.3), 우측(45.3 이상) 분류
        y_zone = "좌측" if y < 22.67 else ("중앙" if y < 45.33 else "우측")
        # x좌표가 극단적으로 상대 쪽(88.5 이상)이면 박스 근처로 특별 분기
        if x >= 88.5:
            x_zone = "박스"
        # 조합된 존 명칭 리턴
        return f"{x_zone}_{y_zone}"


# 분할된 수십/수백 개의 플레이 국면들을 비교군집화(DTW 알고리즘 등)하여 자주 나오는 공격 루트 패턴을 식별하는 클래스
class PatternMiner(Analyzer):
    # 페이즈 목록 전체를 받고, 대표 패턴을 몇 개까지 추출하여 보여줄 것인지 제한점 세팅
    def __init__(self, phases: List[pd.DataFrame], limit: int = 3):
        # 주입받은 페이즈(국면) 뭉치 목록 보관
        self.phases = phases
        # 각 페이즈들의 통계 지표값을 저장할 임시 배열
        self.phase_stats: List[Dict] = []
        # 클라이언트가 요청한 최종 패턴 추출 상한선 저장
        self.limit = limit

    # 개별 페이즈 특성 산출을 위한 내부 헬퍼 래퍼
    def _phase_stats(self, phase: pd.DataFrame) -> Dict:
        analyzer = PhaseAnalyzer(phase)
        return analyzer.phase_stats(phase)

    # 뭉쳐진 모든 페이즈 안을 순회하며 일괄로 통계 스탯을 구해서 리스트로 캐싱
    def feat_list(self):
        self.phase_stats = []
        # 페이즈 순서 인덱싱(i) 처리
        for i, phase in enumerate(self.phases):
            features = self._phase_stats(phase)
            # 메타데이터 참조용 고유 인덱스 번호 마킹
            features["phase_id"] = i
            self.phase_stats.append(features)
        return self.phase_stats

    # 시계열 동적 시간축 왜곡(Dynamic Time Warping) 거리 측정 함수
    # 길이가 다른 두 전개 궤적 시퀀스 간의 물리적인/형태학적인 유사도 차이점을 계산 (작을수록 비슷함)
    def dtw_dist(self, seq_a: np.ndarray, seq_b: np.ndarray) -> float:
        # 두 시퀀스의 길이 측정
        n, m = len(seq_a), len(seq_b)
        # 하나라도 비어있으면 유사도 무한대 (완전 다름) 반환
        if n == 0 or m == 0:
            return float("inf")
        # DTW 계산용 누적 코스트 DP(다이나믹 프로그래밍) 2차원 배열 초기화 (초기값 무한대)
        dp = np.full((n + 1, m + 1), np.inf)
        dp[0, 0] = 0.0
        # 행렬 순회하며 DTW 매칭 알고리즘 가동
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                # 유클리디안 거리 등 두 좌표 시점에서의 벡터 노름(차이) 산출
                cost = np.linalg.norm(seq_a[i - 1] - seq_b[j - 1])
                # 좌, 상, 좌상단으로 향하는 변이 중 가장 코스트가 적게 드는(유사성이 높은) 경로 더하기
                dp[i, j] = cost + min(dp[i - 1, j], dp[i, j - 1], dp[i - 1, j - 1])
        # 양 시퀀스 끝단지점까지 도달하는데 드는 누적 최소 거리 비용 리턴 (시퀀스 패턴 이격성 절대값)
        return float(dp[n, m])

    # 페이즈 안의 선수 액션 출발 위치 (X, Y) 들을 모아 궤적을 잇는 2D 행렬 텐서로 변환
    def phase_seq(self, phase: pd.DataFrame) -> np.ndarray:
        # x좌표 축출 후 넘파이 연속 벡터 배열로 변환
        xs = pd.to_numeric(phase.get("start_x", 0), errors="coerce").fillna(0).to_numpy()
        # y좌표 컬럼 확보 후 벡터 변환
        ys = pd.to_numeric(phase.get("start_y", 0), errors="coerce").fillna(0).to_numpy()
        # [x, y] 2차원 시퀀스 형태로 압착해서 반환
        return np.stack([xs, ys], axis=1)

    # 확보된 모든 국면쌍 간의 거리를 렌더링한 NxN 군집 모델링용 인접 거리 매트릭스 제작
    def dist_mat(self) -> np.ndarray:
        # 우선 모든 페이즈를 시퀀스 벡터 텐서로 치환
        seqs = [self.phase_seq(p) for p in self.phases]
        # 국면 대수
        n = len(seqs)
        # 0점 초기화 NxN 정사각 거리 행렬 구축
        dist = np.zeros((n, n))
        # 상삼각, 하삼각 양방 대칭으로 모든 쌍(Combination) 일대일 DTW 거리 계산 순회
        for i in range(n):
            for j in range(i + 1, n):
                # i 국면과 j 국면 궤적 간의 유사도(비용 거리) 차이 계산
                d = self.dtw_dist(seqs[i], seqs[j])
                # 대칭 행렬 삽입
                dist[i, j] = d
                dist[j, i] = d
        # 계산 끝난 인접 행렬 텐서 반환
        return dist

    # 군집 분석을 수행하여 비슷한 플레이 흐름을 가진 페이즈들을 그루핑
    def cluster_map(self, n_clusters: int = 100) -> Dict:
        # 페이즈별 기초 통계량 스탯 세트업이 아직 안되었다면 호출
        if not self.phase_stats:
            self.feat_list()

        # 표본이 1개 이하여서 클러스터링 분할 연산 자체가 성립 불가면 빠른 리턴
        if len(self.phases) <= 1:
            return {}

        # 클러스터 개수 커스텀 (입력값과 전체 국면 개수 중 작은 쪽 보정)
        n_clusters = min(n_clusters, len(self.phases))
        # N*N DTW 인접 거리 매트릭스 제작
        dist = self.dist_mat()
        # SciPy 계층 클러스터링 알고리즘 투입을 위해 정사각 행렬을 1D 배열(Condensed Distance)로 압축 변환
        condensed = squareform(dist)
        # 완전 기준(Max) 링키지 방식으로 계층적 병합 군집 나무(덴드로그램 트리) 생성
        tree = linkage(condensed, method="complete")
        # 트리를 원하는 클러스터 N개 덩어리로 무 자르듯 분할하여 각 데이터의 레이블 확보
        labels = fcluster(tree, t=n_clusters, criterion="maxclust")

        # 각 그룹별 속성 및 통계를 담을 클러스터 정보 딕셔너리 포맷팅
        clusters: Dict[int, Dict] = {}
        for i, label in enumerate(labels):
            if label not in clusters:
                # 첫 등장이면 자료구조 초기 셋업
                clusters[label] = {
                    "phases": [], # 그룹에 속한 페이즈들의 원본 인덱스
                    "count": 0, # 소속 페이즈 개수 빈도
                    "shot_phases": 0, # 이 전술 기동 속에서 슈팅을 파생시킨 빈도
                    "shot_total": 0, # 총 슈팅 시도 건수 누합
                    "action_total": 0, # 모든 전계 파생 액션들의 종합 개수수
                    "avg_features": {}, # 평균적 속성 수치 요약
                }
            # 마킹
            clusters[label]["phases"].append(i)
            clusters[label]["count"] += 1
            # 기 추출했던 단일 페이즈 속성 캐시에서 정보 채굴
            shot_count = int(self.phase_stats[i].get("shot_count", 0))
            action_count = int(self.phase_stats[i].get("length", 0))
            clusters[label]["shot_total"] += shot_count
            clusters[label]["action_total"] += action_count
            # 슈팅이 한번이라도 시도된 국면이라면 기회 제공 판단 누적
            if shot_count > 0:
                clusters[label]["shot_phases"] += 1

        # 클러스터 특성 파악을 위해 평균을 매길 주요 속성 키 명단
        feature_cols = [
            "length", "duration", "start_x", "start_y",
            "end_x", "end_y", "avg_x", "avg_y",
            "pass_count", "carry_count", "forward_progress", "lateral_movement",
        ]
        
        # 합산된 클러스터들을 돌면서 그룹별 평균 통계 재산출
        for label in clusters:
            phase_indices = clusters[label]["phases"]
            for col in feature_cols:
                # 소속 파편 페이즈들의 스탯 평균 내기
                clusters[label]["avg_features"][col] = float(
                    np.mean([self.phase_stats[i].get(col, 0) for i in phase_indices])
                )
            # 패턴 내 액션 수 대비 슈팅 발생 비율(전환율/효율성) 통계 공식화
            clusters[label]["shot_conversion_rate"] = clusters[label]["shot_total"] / max(
                clusters[label]["action_total"], 1
            )

        # 완성된 거시적 군집 생태계 딕셔너리 반환
        return clusters

    # 도출된 여러 클러스터 그룹 중 득점 기대 확률 등 핵심 성능이 가장 뛰어난 Top N개 루트 추출
    def pattern_top(self, n_top: int = 3) -> List[Dict]:
        # 군집 매핑 엔진 구동
        clusters = self.cluster_map()
        if not clusters:
            return []

        # 클러스터(패턴 그룹들)를 슈팅 도합량 및 전환율(효율) 내림차순 기준으로 줄세워서 최상급 전술 먼저 파악
        sorted_clusters = sorted(
            clusters.items(), key=lambda x: (x[1]["shot_total"], x[1]["shot_conversion_rate"]), reverse=True
        )

        # 분석 완료된 대표 패턴 리포트 리스트
        patterns: List[Dict] = []
        for label, info in sorted_clusters[:n_top]:
            # 그룹 내 파편 이벤트들을 자연어 전개 텍스트 리스트(시퀀스)화 시킴
            sequences = [self.phase_code(self.phases[i]) for i in info["phases"]]
            # 해당 전술에서 가장 자주 나타나는 행동 순서 패턴(A->B->C 패스 연계 경로 등) 랭킹
            common = self.seq_freq(sequences)

            # 프론트엔드가 렌더링할 포맷으로 대표 패턴 요약 객체 완성하여 리스트 푸쉬
            patterns.append(
                {
                    "cluster_id": int(label), # 패턴 ID
                    "frequency": info["count"], # 발동 횟수
                    "shot_total": int(info["shot_total"]), # 창출 슈팅 수
                    "shot_conversion_rate": round(info["shot_conversion_rate"], 3), # 타격 전환 효율
                    "avg_duration": round(info["avg_features"].get("duration", 0), 1), # 평균 지연 시간(초)
                    "avg_passes": round(info["avg_features"].get("pass_count", 0), 1), # 투입 평균 패스
                    "avg_forward_progress": round(info["avg_features"].get("forward_progress", 0), 1), # 추진 깊이
                    "avg_start_zone": self.zone_tag(
                        info["avg_features"].get("start_x", 0),
                        info["avg_features"].get("start_y", 0),
                    ), # 시발점 섹터 태그
                    "avg_end_zone": self.zone_tag(
                        info["avg_features"].get("end_x", 0),
                        info["avg_features"].get("end_y", 0),
                    ), # 마무리된 섹터 태그
                    "common_sequences": common[:3], # 상세 자연어 전개 설명 최상위 루트 3건
                }
            )

        # 탑 패턴 도출본 전체 객체 반환
        return patterns

    # Analyzer 요구 스펙 맞춤 출력 퍼사드
    def data(self) -> List[Dict]:
        return self.pattern_top(self.limit)

    # 좌표값을 문자열 섹터로 태깅 변환
    def zone_tag(self, x: float, y: float) -> str:
        x_zone = "수비" if x < 35 else ("중앙" if x < 70 else "공격")
        y_zone = "좌측" if y < 22.67 else ("중앙" if y < 45.33 else "우측")
        if x >= 88.5:
            x_zone = "박스"
        return f"{x_zone}_{y_zone}"

    # Phase 내부의 이벤트 로우데이터를 가독성 높은 자연어 문자 배열로 번역하는 토크나이저
    def phase_code(self, phase: pd.DataFrame) -> List[str]:
        # SPADL 표준 지표 구조로 타입 변형 보정
        phase = spadl_map(phase)
        phase = action_rows(phase)
        # 번역된 언어 토큰 스트링 리스트
        encoded: List[str] = []
        # 페이즈 내부 이벤트 열차 순회
        for _, event in phase.iterrows():
            # SPADL 공통 액션 이름 가져오고
            action = str(event.get("spadl_type", event.get("type_name", "action")))
            # 좌표 할당
            sx = float(event.get("start_x", 0) or 0)
            sy = float(event.get("start_y", 0) or 0)
            ex = float(event.get("end_x", sx) or sx)
            ey = float(event.get("end_y", sy) or sy)
            # 출발지 도착지 존 텍스트 파싱
            start_zone = self.zone_tag(sx, sy)
            end_zone = self.zone_tag(ex, ey)

            # 출발/도착이 명확히 구별되고 궤적이 의미 있는 행위인지 분류
            if action in {"pass", "cross", "corner_crossed", "freekick_crossed", "throw_in", "goal_kick", "dribble"}:
                # 출발지점부터 도착지점까지 동선 포함 텍스트 토큰 제작 (ex: pass FROM 중원 TO 상대박스)
                token = f"{action} FROM {start_zone} TO {end_zone}"
            else:
                # 슛이나 클리어링 같이 특정 지점(AT) 자체 행위가 중요한 액션 텍스트 토큰 제작
                token = f"{action} AT {start_zone}"
            encoded.append(token)
        # 나열된 국면 스토리 텍스트 반환
        return encoded

    # N-Gram 유사도 분석처럼, 연속된 문자열 시퀀스 배열 중 빈도수가 높은 특정 구간 순서를 파악해 뽑아내는 알고리즘
    def seq_freq(self, sequences: List[List[str]]) -> List[str]:
        if not sequences:
            return []

        # 패턴으로 취급하기 위해 검출되어야 할 타당한 상위 지지율 최소치(10%) 계산
        min_support = max(2, int(len(sequences) * 0.1))
        # 연속된 패턴을 찾을 최대 체인 길이(예: 4단 논법 패스 워크까지)
        max_len = 4
        # 특정 서브 시퀀스 토큰 체인의 출현을 해시화 카운팅
        support_counter: Counter = Counter()

        # 각 개별 문자열 배열 순회
        for seq in sequences:
            seq_len = len(seq)
            # 중복 집계를 방지하기 위해 1국면 1패턴 단일 인정 세트 구성
            seen = set()
            # 2연계 동작부터 체인 길이 4연계 동작 루프
            for length in range(2, min(max_len, seq_len) + 1):
                # 조합 생성기 재귀 함수를 이용해 인덱싱 포지션 추출 (예: [0,1], [1,2] 등)
                for idxs in _seq_idx(seq_len, length):
                    # 연속 순서열로 패킹
                    pattern = tuple(seq[i] for i in idxs)
                    seen.add(pattern)
            # 한 페이즈 안에서 나온 모든 유니크 부분 패턴열을 카운터 원장에 병합 기록
            for pattern in seen:
                support_counter[pattern] += 1

        # 빈도 점수를 스코어 산정 방식으로 최종 채점하기 위한 중간 버퍼
        scored = []
        for pattern, support in support_counter.items():
            # 최소 지지율 방어선을 넘지 못하면 마이너한 우연으로 취급하고 버림
            if support < min_support:
                continue
            # 순수 빈도 횟수 * 특정 액션 연계 가중치 점수 합산 로직 (가치 분석)
            score = support * seq_weight(pattern)
            scored.append((score, support, pattern))

        # 가중치 점수 내림차순, 그리고 지원 빈도 내림차순으로 겹 정렬
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        # 상위 10개만 골라서, 읽기 편하게 'A -> B -> C' 형식으로 조립 후 반환
        return [" -> ".join(pat) for _, _, pat in scored[:10]]


# 국면 길이에 맞춰 연속된 체인 길이를 만족하는 조합 쌍의 인덱스 모음을 제공하는 조합 재귀 제네레이터
def _seq_idx(n: int, length: int) -> Iterable[Tuple[int, ...]]:
    # 에러 및 예외 가드
    if length <= 0 or n < length:
        return []
    indices = list(range(n))
    if length == 1:
        return [(i,) for i in indices]
    result = []

    # 조합 및 순열 노드 탐색 재귀 함수
    def rec(start: int, path: List[int]):
        # 원하는 길이에 도달 시 루트 탈출 및 결과 수확
        if len(path) == length:
            result.append(tuple(path))
            return
        # 노드 깊이 탐색 진행
        for i in range(start, n):
            rec(i + 1, path + [i])

    rec(0, [])
    return result

# 추출된 부분 전술 패턴 열에 대해 행동 유형별로 가산점을 주어 우선도가 높은 핵심 패턴인지 가중치를 채점
def seq_weight(pattern: Tuple[str, ...]) -> float:
    # 슛, 패스 등 중요 액션에 대한 배점 잣대 기준 테이블 세팅
    weights = {
        "shot": 2.0,
        "pass": 0.5,
    }
    # 초기 스코어
    score = 0.0
    # 패턴 배열을 돌며 행동 타입명 추출 (ex: 'pass FROM 중원' -> 분할 시 첫단락 단어인 'pass')
    for token in pattern:
        action = token.split()[0]
        # 딕셔너리 기준 가중 점수 합산, 매핑에 없으면 기본 1.0 더함
        score += weights.get(action, 1.0)
    # 총 합 리턴
    return score

# 외부 호출 시 경기 이벤트를 던져넣고 즉시 탑 전술 패턴 N건을 뽑아갈 수 있음
def team_pat(events_df: pd.DataFrame, team_id: int, n_patterns: int = 3) -> List[Dict]:
    # 이벤트 데이터를 SPADL 규격으로 전개 보정 정규화 수행
    events_df = action_rows(events_df)
    
    # 국면 분할 코어 돌려서 잘게 썰기
    analyzer = PhaseAnalyzer(events_df)
    phases = analyzer.phase_list()
    if not phases:
        return []

    # 전체 공방 페이즈 중 분석 주권 팀이 행동을 시작하는 페이즈만 걸러내기
    team_phases = [p for p in phases if int(p.iloc[0].get("team_id", -1)) == int(team_id)]
    if not team_phases:
        return []

    # O(N^2) 시간을 그리는 DTW 연산 과부하가 걸리지 않도록 연산 상한 캡 리미트 제한치 설정
    max_phases = 200
    if len(team_phases) > max_phases:
        # 페이즈 중 공격의 의미가 있었을 법한(Shot 슈팅 포함) 국면들의 인덱스를 우선 발췌
        shot_idx = [
            i
            for i, p in enumerate(team_phases)
            if "type_name" in p.columns and (p["type_name"] == "Shot").any()
        ]
        
        # 최우선 보존 대상
        keep = shot_idx
        # 슈팅 페이즈만으로 이미 상한을 초과한다면, 이벤트 액션 길이가 더 긴 (더 짜임새가 있어 보이는) 페이즈 순서로 자름
        if len(keep) > max_phases:
            keep = sorted(keep, key=lambda i: len(team_phases[i]), reverse=True)[:max_phases]
        else:
            # 상한 캡 안쪽에 도달해 여유 캐파가 있다면, 미달분을 슈팅 없는 일반 페이즈 중 길이가 긴 순위들로 마저 채움
            extra = max_phases - len(keep)
            if extra > 0:
                other = [i for i in range(len(team_phases)) if i not in set(keep)]
                other = sorted(other, key=lambda i: len(team_phases[i]), reverse=True)[:extra]
                keep = keep + other
        
        # 중복 방지 및 인덱스 정렬
        keep = sorted(set(keep))
        # 최적으로 솎아진 최대 200개 규모의 대표 페이즈만 할당
        team_phases = [team_phases[i] for i in keep]

    # 클러스터링 알고리즘 통과시키고 도출된 n개의 데이터 송출
    miner = PatternMiner(team_phases, n_patterns)
    return miner.data()


# 캐싱 진입점: (team_id, n_games, top_k, mark) 기준 메모이즈
# L1(메모리 single-flight) + L2(DiskCache pickle) 2단 — 재시작 후에도 L2 hit으로 콜드 스타트 회피
@layered_cache("pat", maxsize=256)
def pat_box(team_id: int, n_games: int, top_k: int, mark: tuple) -> List[Dict]:
    from ..core.data import match_events
    events = match_events(team_id, n_games, include_opponent=True, normalize_mode="team")
    if len(events) == 0:
        return []
    return team_pat(events, team_id, top_k)
