# 경기 시뮬레이터 - 확률 모델 기반 승부 예측 및 전술 시나리오
from __future__ import annotations
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, List
import numpy as np
import pandas as pd
from .spec import SimState, Rule
from .rules import RULES
from ..core.data import matches, match_events
from ..core.spadl import action_rows, side_norm
from ..vaep.model import prob_vals

DECAY = 0.85 # 과거 경기 데이터에 대한 시계열 감가상각 가중치
MAX_GOALS = 7 # 시뮬레이션 양팀 최대 득점 스케일 캡
RHO = 0.08 # 양팀 득점 상호 의존도 관련 계수

# 기본 수치 정리 헬퍼
def num(val, default=0.0):
    if val is None:
        return default
    try:
        result = float(val)
        # NaN이나 무한대 값 쳐내기
        return default if math.isnan(result) or math.isinf(result) else result
    except Exception:
        return default

# 단일 팀의 경기 시뮬레이션 핵심 기초 척도들을 담아두는 데이터 청사진
@dataclass
class Stat:
    team_id: int # 분석 대상 팀 ID
    games: int # 표본 경기 수
    xg_for: float # 누적 기대 득점(xG)
    xg_against: float # 누적 기대 실점(xG Against)
    shots_for: int # 누적 슈팅 횟수
    shots_against: int # 누적 허용 슈팅 수
    pass_for: float # 패스 성공률
    pass_against: float # 허용(상대) 패스 성공률
    poss: float # 점유율 추정치
    metrics: Dict[str, float] # 기타 VAEP 파생 지표 모음

    # 경기당 평균 기대 득점 반환 프로퍼티
    @property
    def xg_for_pg(self) -> float:
        return self.xg_for / max(self.games, 1)

    # 경기당 평균 기대 실점 반환 프로퍼티
    @property
    def xg_against_pg(self) -> float:
        return self.xg_against / max(self.games, 1)

# Stat 객체를 산출해내는 통계 클래스
class StatBox:
    def __init__(self, events: pd.DataFrame, team_id: int):
        self.team_id = team_id
        self.events = events

    # 경기 날짜 최신순으로 정렬해서 과거 경기일수록 영향력 페널티 부과 가중치 배열 생성
    def _w(self, events: pd.DataFrame) -> np.ndarray:
        if events.empty:
            return np.array([])
        # 전체 경기 메타데이터에서 날짜 뼈대 가져오기
        match_df = matches()[["game_id", "game_date"]].copy()
        match_df["game_date"] = pd.to_datetime(match_df["game_date"], errors="coerce")
        # 경기 ID -> 날짜 매핑
        date_map = match_df.set_index("game_id")["game_date"].to_dict()
        
        # 주입받은 이벤트 표본에 포함된 경기들 식별
        game_ids = events["game_id"].dropna().unique().tolist()
        games = []
        for gid in game_ids:
            games.append((gid, date_map.get(gid)))
            
        # 날짜 최신순 정렬
        games.sort(key=lambda x: (pd.isna(x[1]), x[1]), reverse=True)
        # 1등(최신)부터 N등까지의 오더 딕셔너리
        order = {gid: idx for idx, (gid, _) in enumerate(games)}
        
        # 0.85 ^ (최신순 랭킹) 형태로 이전 경기들의 비중을 깎는 넘파이 배열 반환
        return events["game_id"].map(lambda g: DECAY ** order.get(g, 0)).fillna(1.0).to_numpy()

    # 이벤트 로우 컬럼이 슈팅인지 판별하는 불리언 마스크
    def _shot(self, events: pd.DataFrame) -> pd.Series:
        if "spadl_type" in events.columns:
            return events["spadl_type"].fillna("").str.lower().eq("shot")
        return events.get("type_name", "").fillna("").eq("Shot")

    # 이 팀의 패스 성공률 추출
    def _pass(self, events: pd.DataFrame, team_mask: pd.Series) -> float:
        if "type_name" not in events.columns:
            return 0.0
        # 조건에 맞는 해당 팀의 퓨어 패스 이벤트만 추출
        passes = events[team_mask & (events["type_name"] == "Pass")]
        if passes.empty:
            return 0.0
        # 성공 판정 받은 패스 개수
        success = passes[passes.get("result_name", "") == "Successful"]
        return len(success) / max(len(passes), 1)

    # 내부 로직 배합하여 최종 팀 Stat 통계 집계본을 조립해 내보냄
    def box(self) -> Stat:
        # 잡음 방지: 유효 SPADL 액션만 남김
        events = action_rows(self.events)
        # 좌표 일치화
        events = side_norm(events, matches())
        # 순서 무결성 부여
        events = events.sort_values(["game_id", "period_id", "time_seconds", "action_id"]).reset_index(drop=True)
        
        # VAEP 핵심 모델: 모든 일련의 과정에 대한 득점/실점 기대 가치 머신러닝 산출
        p_score, _, metrics = prob_vals(events)
        if len(p_score) != len(events):
            p_score = np.resize(p_score, len(events))
        # 도출된 기대 득점 기여도를 컬럼으로 심기
        events["p_score"] = p_score
        
        # 최근 경기일수록 가중치 더 큰 웨이트 배열 덮어쓰기
        weights = self._w(events)
        events["w"] = weights
        
        # 자 팀과 상대 팀 피아 식별 마스크
        team_mask = events["team_id"] == self.team_id
        # 전체 슈팅 이벤트 마스크
        shot_mask = self._shot(events)
        
        # 기대 득점(xG) 계산 = 내 슈팅 찬스의 골 밸류(p_score) * 경기 최신 가중치 누적
        xg_for = float((events.loc[team_mask & shot_mask, "p_score"] * events.loc[team_mask & shot_mask, "w"]).sum())
        # 허용 기대 실점 계산 = 상대 슈팅 찬스의 밸류 * 가중치 누적
        xg_against = float((events.loc[~team_mask & shot_mask, "p_score"] * events.loc[~team_mask & shot_mask, "w"]).sum())
        
        # 단순 빈도 텍스트 스탯들
        shots_for = int((team_mask & shot_mask).sum())
        shots_against = int((~team_mask & shot_mask).sum())
        pass_for = self._pass(events, team_mask)
        pass_against = self._pass(events, ~team_mask)
        
        # 가중치 섞인 누적 행동 횟수로 팀 활동(점유) 장악력 산출
        poss = float(events.loc[team_mask, "w"].sum() / max(events["w"].sum(), 1.0))
        # 처리된 순수 경기 개수
        games = int(events["game_id"].nunique() or 1)
        
        # 생성된 데이터 클래스 던짐
        return Stat(
            team_id=self.team_id,
            games=games,
            xg_for=xg_for,
            xg_against=xg_against,
            shots_for=shots_for,
            shots_against=shots_against,
            pass_for=pass_for,
            pass_against=pass_against,
            poss=poss,
            metrics=metrics,
        )

# Dixon-Coles 승부 예측 확률 모형 계산기
class Prob:
    def __init__(self, lam_for: float, lam_against: float, rho: float = RHO):
        # 우리 팀의 득점 확률 인자
        self.lam_for = max(0.05, lam_for)
        # 우리 팀의 실점 확률 인자
        self.lam_against = max(0.05, lam_against)
        # 상호 의존성(0-0 무승부 증가) 계수
        self.rho = max(0.0, rho)

    # MAX_GOALS까지의 모든 스코어별 일어날 확률 그리드를 반환
    def grid(self, max_goal: int = MAX_GOALS) -> np.ndarray:
        # 양 팀 득점이 아예 안나왔을 때의 보정계수 코어
        lam3 = self.rho * math.sqrt(self.lam_for * self.lam_against)
        n = max_goal
        idx = np.arange(n + 1)
        
        # 행/열 매트릭스를 그리기 위한 2D 벡터화 브로드캐스트 매핑
        i = idx[:, None]
        j = idx[None, :]
        
        # 팩토리얼 미리 연산 캐싱
        fact = np.array([math.factorial(x) for x in range(n + 1)], dtype=float)
        p = np.zeros((n + 1, n + 1), dtype=float)
        
        # 푸아송 분포 베이스 익스포넨셜 마진
        base = math.exp(-(self.lam_for + self.lam_against + lam3))
        
        # Dixon-Coles 코어: k=0부터 이중 푸아송 근사에 디펜던시를 줘서 순회
        for k in range(n + 1):
            i_k = np.clip(i - k, 0, n)
            j_k = np.clip(j - k, 0, n)
            mask = (i >= k) & (j >= k)
            
            # 수학적 확률 질량 함수
            term = (self.lam_for ** (i - k)) * (self.lam_against ** (j - k))
            term = term * (lam3 ** k) / (fact[i_k] * fact[j_k] * fact[k])
            p += np.where(mask, term, 0.0)
            
        p *= base
        total = p.sum()
        # 근사된 전체 확률 100% 정규화
        if total > 0:
            p = p / total
        return p

    # 승/무/패 퍼센테이지를 응축해서 리턴
    def out(self) -> Dict[str, float]:
        mat = self.grid()
        # 행렬의 우상단(내 골수 > 상대 골수) 삼각행렬 합산 = 승리 확률
        win = float(mat[np.triu_indices_from(mat, 1)].sum())
        # 행렬의 대각선(골수 동일) 합산 = 무승부 확률
        draw = float(np.trace(mat))
        # 행렬의 좌하단(결과 뒤집힘) = 패배 확률
        lose = float(mat[np.tril_indices_from(mat, -1)].sum())
        
        # % 스케일로 예쁘게 라운딩
        return {
            "win": round(num(win * 100), 1),
            "draw": round(num(draw * 100), 1),
            "lose": round(num(lose * 100), 1),
        }

# 경기를 앞두고 양팀 전력을 비교, 모의 시뮬레이션을 돌려 결과를 추정하는 분석기 클래스
class Sim:
    def __init__(
        self,
        our_id: int, # 홈(우리)팀
        opp_id: int, # 어웨이(상대)팀
        n_games: int, # 탐방할 과거 경기수
        our_stat: Stat | None = None, # 외부주입용 캐시 스탯
        opp_stat: Stat | None = None,
        our_events: pd.DataFrame | None = None,
        opp_events: pd.DataFrame | None = None,
    ):
        self.our_id = our_id
        self.opp_id = opp_id
        self.n_games = n_games
        
        # 외부 주입이 없으면 직접 쿼리하여 이벤트 적재 (가장 무거운 구간)
        self.our_events = our_events if our_events is not None else match_events(our_id, n_games, include_opponent=True, spadl=True)
        self.opp_events = opp_events if opp_events is not None else match_events(opp_id, n_games, include_opponent=True, spadl=True)
        # 이벤트 토대 양팀 누적 스코어 분석 산출
        self.our = our_stat if our_stat is not None else StatBox(self.our_events, our_id).box()
        self.opp = opp_stat if opp_stat is not None else StatBox(self.opp_events, opp_id).box()
        
        # 이 시뮬레이션 환경의 현재 팩트(양팀 기초 전력) 규격화
        self.state = SimState(
            xg_for=self.our.xg_for_pg,
            xg_against=self.our.xg_against_pg,
            pass_for=self.our.pass_for,
            pass_against=self.opp.pass_for,
            poss=self.our.poss,
        )
        
        # 적용 가능한 AI 권장 전술 룰 세팅
        self.rules: List[Rule] = list(RULES)
        self.rule_keys = [rule.data(self.state).get("key") for rule in self.rules]
        self.rule_map = {key: rule for key, rule in zip(self.rule_keys, self.rules) if key}

    # 양 팀 공방 xG 스탯을 조합하여 해당 매치의 기본 기대 득점/실점 평균 람다(Lambda) 모델 배정
    def _avg(self) -> tuple[float, float]:
        # '우리의 득점력'과 '상대의 실점력'의 반반 조합 = 최종 득점 기대치
        lam_for = (self.our.xg_for_pg + self.opp.xg_against_pg) / 2
        # '우리의 실점률'과 '상대의 득점력'의 반반 조합 = 최종 실점 기대치
        lam_against = (self.our.xg_against_pg + self.opp.xg_for_pg) / 2
        
        # 경기당 0.2 이하면 시스템 계산 에러를 낳을 수 있으므로 하한 보정
        lam_for = max(0.2, lam_for)
        lam_against = max(0.2, lam_against)
        return lam_for, lam_against

    # '전술'을 기용했을 때 위 기본 람다(득실기대치)를 흔들어버리는 계수 적용
    def _factor(self, lam_for: float, lam_against: float, rules: List[Rule]) -> tuple[float, float]:
        # 특정 전술이 시전될 때 부여되는 우리 득점력(Up) 상승폭과 상대 득점력(Down) 억제폭 가중치
        factors = {
            "press_hub": (1.02, 0.92), # 압박: 득점 +2%, 실점 -8%
            "counter_setpiece": (1.01, 0.95), # 역습대비: 득점 +1%, 실점 -5%
            "exploit_pattern": (1.05, 0.98), # 약점공략: 득점 +5%, 실점 -2%
        }
        # 현재 활성화된 룰들을 순회 적용하며 증폭치 곱연산
        for rule in rules:
            key = rule.data(self.state).get("key")
            if key in factors:
                up, down = factors[key]
                lam_for *= up
                lam_against *= down
        return lam_for, lam_against

    # 별도 전술을 적용하지 않은 순수한 양 팀 체급 스탯 기반 승무패 시뮬레이터 결과 도출
    def base(self) -> Dict[str, float]:
        lam_for, lam_against = self._avg()
        return Prob(lam_for, lam_against).out()

    # 우리가 추천하는 전술 제안(opt)을 모두 영혼까지 끌어 모았을 때 나올 수 있는 승무패 예측치
    def opt(self) -> Dict[str, float]:
        lam_for, lam_against = self._avg()
        lam_for, lam_against = self._factor(lam_for, lam_against, self.rules)
        return Prob(lam_for, lam_against).out()

    # 특정 단일 전술(혹은 전체)을 집어넣었을 때 얼마나 승률이 요동치는지(before & after) 뽑는 리포트용 메서드
    def case(self, scenario: str) -> Dict:
        # Before 측정
        base_prob = self.base()
        
        if scenario == "all_tactics":
            label = "종합 전술 적용"
            desc = "모든 분석 기반 전술 동시 적용"
            # 룰 전부 먹임
            rule_list = self.rules
        else:
            # 단일 시나리오 탐색 및 추출
            rule = self.rule_map.get(scenario)
            entry = rule.data(self.state) if rule else None
            # 메타데이터 레이블 파싱
            label = entry.get("scenario", {}).get("name") if entry else "종합 전술 적용"
            desc = entry.get("scenario", {}).get("description") if entry else "모든 분석 기반 전술 동시 적용"
            rule_list = [rule] if rule else self.rules
            
        # After 마개조 측정
        lam_for, lam_against = self._avg()
        lam_for, lam_against = self._factor(lam_for, lam_against, rule_list)
        new_prob = Prob(lam_for, lam_against).out()
        
        # Before & After 비교 견적서 반환
        return {
            "scenario": label,
            "description": desc,
            "before": base_prob,
            "after": new_prob,
            # 승률 개선치 (순증가치)
            "win_change": round(num(new_prob["win"] - base_prob["win"]), 1),
            # 자연어 코멘트 피드백
            "recommendation": self.memo(base_prob, new_prob),
        }

    # 승률 증가치에 맞추어 클라이언트(감독님)가 볼 1줄 다이내믹 피드백 작성
    def memo(self, before: Dict, after: Dict) -> str:
        win_change = after["win"] - before["win"]
        if win_change >= 10:
            return "✅ 강력 추천: 이 전술 조합으로 승률이 크게 상승합니다."
        if win_change >= 5:
            return "👍 추천: 전술 적용 시 승률 개선이 예상됩니다."
        if win_change >= 0:
            return "ℹ️ 참고: 소폭의 승률 개선이 가능합니다."
        # 마이너스 나는 똥전술이면
        return "⚠️ 주의: 이 전술은 현재 상황에 적합하지 않을 수 있습니다."

    # 기초 통계 수치를 베이스로 뻔하게 떨어지는 약점 공략법(휴리스틱)을 나열
    def hint(self) -> List[Dict]:
        tips: List[Dict] = []
        
        # 상대 패스웍이 뛰어나면 압박 제언
        if self.opp.pass_for > 0.78:
            tips.append({
                "priority": 1,
                "tactic": "중원 압박 강화",
                "reason": f"상대 패스 성공률 {self.opp.pass_for * 100:.0f}%",
                "expected_effect": "빌드업 차단으로 실점 기대치 감소",
                "win_prob_change": "+5%p",
            })
            
        # 상대 공격력이 좋으면 수비 제언
        if self.opp.xg_for_pg > 1.25:
            tips.append({
                "priority": 2,
                "tactic": "수비 라인 낮추기",
                "reason": f"상대 경기당 xG {self.opp.xg_for_pg:.2f}",
                "expected_effect": "박스 침투 억제",
                "win_prob_change": "+3%p",
            })
            
        # 우리 공격력이 약하면 역습 효율 제언
        if self.our.xg_for_pg < 1.05:
            tips.append({
                "priority": 3,
                "tactic": "역습 집중 전술",
                "reason": f"우리 경기당 xG {self.our.xg_for_pg:.2f}",
                "expected_effect": "전환 공격 효율 개선",
                "win_prob_change": "+4%p",
            })
            
        # 특징이 고만고만해서 아무 팁도 안 나갔으면 균형 전술 추천
        if not tips:
            tips.append({
                "priority": 1,
                "tactic": "균형 잡힌 전술 유지",
                "reason": "양팀 기대 득실 균형",
                "expected_effect": "안정적인 경기 운영",
                "win_prob_change": "±0%p",
            })
        return sorted(tips, key=lambda x: x["priority"])


# 최상단 진입점: 프리매치 페이지 로딩 시 던지는 종합 패키지 리스폰스 제조기
def prematch(our_events: pd.DataFrame, opponent_events: pd.DataFrame) -> Dict:
    # 빈 데이터면 빈 껍데기 반환
    if our_events.empty or opponent_events.empty:
        return {
            "base_prediction": {"win": 0.0, "draw": 0.0, "lose": 0.0},
            "optimal_prediction": {"win": 0.0, "draw": 0.0, "lose": 0.0},
            "win_improvement": 0.0,
            "tactical_suggestions": [],
            "scenarios": [],
        }
        
    # 홈, 어웨이 양팀 ID 구하기
    our_id = int(our_events["team_id"].iloc[0])
    opp_id = int(opponent_events["team_id"].iloc[0])
    # 양 팀 각각 몇경기 표본인지 가져옴
    n_games = int(max(our_events["game_id"].nunique(), opponent_events["game_id"].nunique(), 1))
    
    # 시간 단축을 위해 우리 팀 분석과 상대 팀 분석을 각각 2개 코어로 병렬화 멀티스레드 태움
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_our = pool.submit(StatBox(our_events, our_id).box)
        fut_opp = pool.submit(StatBox(opponent_events, opp_id).box)
        # 퓨처 결과 대기 후 픽업
        our_stat = fut_our.result()
        opp_stat = fut_opp.result()
        
    # 엔진 할당 및 파워온
    sim = Sim(our_id, opp_id, n_games, our_stat=our_stat, opp_stat=opp_stat, our_events=our_events, opp_events=opponent_events)
    # 기본 승률 스캔
    base_prob = sim.base()
    # 최고점 승률 스캔
    opt_prob = sim.opt()
    # 각종 개별 전술별 Before-After 세부 시나리오 분석 목록 스크랩
    scenarios = [sim.case(s) for s in sim.rule_keys + ["all_tactics"]]
    
    # 조립해서 외부 배출
    return {
        "base_prediction": base_prob,
        "optimal_prediction": opt_prob,
        "win_improvement": round(num(opt_prob["win"] - base_prob["win"]), 1),
        "tactical_suggestions": sim.hint(),
        "scenarios": scenarios,
    }
