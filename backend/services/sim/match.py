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

DECAY = 0.85
MAX_GOALS = 7
RHO = 0.08


# 기본 수치 정리
def num(val, default=0.0):
    if val is None:
        return default
    try:
        result = float(val)
        return default if math.isnan(result) or math.isinf(result) else result
    except Exception:
        return default


@dataclass
class Stat:
    team_id: int
    games: int
    xg_for: float
    xg_against: float
    shots_for: int
    shots_against: int
    pass_for: float
    pass_against: float
    poss: float
    metrics: Dict[str, float]

    @property
    def xg_for_pg(self) -> float:
        return self.xg_for / max(self.games, 1)

    @property
    def xg_against_pg(self) -> float:
        return self.xg_against / max(self.games, 1)


class StatBox:
    def __init__(self, events: pd.DataFrame, team_id: int):
        self.team_id = team_id
        self.events = events

    def _w(self, events: pd.DataFrame) -> np.ndarray:
        if events.empty:
            return np.array([])
        match_df = matches()[["game_id", "game_date"]].copy()
        match_df["game_date"] = pd.to_datetime(match_df["game_date"], errors="coerce")
        date_map = match_df.set_index("game_id")["game_date"].to_dict()
        game_ids = events["game_id"].dropna().unique().tolist()
        games = []
        for gid in game_ids:
            games.append((gid, date_map.get(gid)))
        games.sort(key=lambda x: (pd.isna(x[1]), x[1]), reverse=True)
        order = {gid: idx for idx, (gid, _) in enumerate(games)}
        return events["game_id"].map(lambda g: DECAY ** order.get(g, 0)).fillna(1.0).to_numpy()

    def _shot(self, events: pd.DataFrame) -> pd.Series:
        if "spadl_type" in events.columns:
            return events["spadl_type"].fillna("").str.lower().eq("shot")
        return events.get("type_name", "").fillna("").eq("Shot")

    def _pass(self, events: pd.DataFrame, team_mask: pd.Series) -> float:
        if "type_name" not in events.columns:
            return 0.0
        passes = events[team_mask & (events["type_name"] == "Pass")]
        if passes.empty:
            return 0.0
        success = passes[passes.get("result_name", "") == "Successful"]
        return len(success) / max(len(passes), 1)

    # 팀 지표 계산
    def box(self) -> Stat:
        events = action_rows(self.events)
        events = side_norm(events, matches())
        events = events.sort_values(["game_id", "period_id", "time_seconds", "action_id"]).reset_index(drop=True)
        p_score, _, metrics = prob_vals(events)
        if len(p_score) != len(events):
            p_score = np.resize(p_score, len(events))
        events["p_score"] = p_score
        weights = self._w(events)
        events["w"] = weights
        team_mask = events["team_id"] == self.team_id
        shot_mask = self._shot(events)
        xg_for = float((events.loc[team_mask & shot_mask, "p_score"] * events.loc[team_mask & shot_mask, "w"]).sum())
        xg_against = float((events.loc[~team_mask & shot_mask, "p_score"] * events.loc[~team_mask & shot_mask, "w"]).sum())
        shots_for = int((team_mask & shot_mask).sum())
        shots_against = int((~team_mask & shot_mask).sum())
        pass_for = self._pass(events, team_mask)
        pass_against = self._pass(events, ~team_mask)
        poss = float(events.loc[team_mask, "w"].sum() / max(events["w"].sum(), 1.0))
        games = int(events["game_id"].nunique() or 1)
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


class Prob:
    def __init__(self, lam_for: float, lam_against: float, rho: float = RHO):
        self.lam_for = max(0.05, lam_for)
        self.lam_against = max(0.05, lam_against)
        self.rho = max(0.0, rho)

    # 득점 확률 그리드
    def grid(self, max_goal: int = MAX_GOALS) -> np.ndarray:
        lam3 = self.rho * math.sqrt(self.lam_for * self.lam_against)
        n = max_goal
        idx = np.arange(n + 1)
        i = idx[:, None]
        j = idx[None, :]
        fact = np.array([math.factorial(x) for x in range(n + 1)], dtype=float)
        p = np.zeros((n + 1, n + 1), dtype=float)
        base = math.exp(-(self.lam_for + self.lam_against + lam3))
        for k in range(n + 1):
            i_k = np.clip(i - k, 0, n)
            j_k = np.clip(j - k, 0, n)
            mask = (i >= k) & (j >= k)
            term = (self.lam_for ** (i - k)) * (self.lam_against ** (j - k))
            term = term * (lam3 ** k) / (fact[i_k] * fact[j_k] * fact[k])
            p += np.where(mask, term, 0.0)
        p *= base
        total = p.sum()
        if total > 0:
            p = p / total
        return p

    def out(self) -> Dict[str, float]:
        mat = self.grid()
        win = float(mat[np.triu_indices_from(mat, 1)].sum())
        draw = float(np.trace(mat))
        lose = float(mat[np.tril_indices_from(mat, -1)].sum())
        return {
            "win": round(num(win * 100), 1),
            "draw": round(num(draw * 100), 1),
            "lose": round(num(lose * 100), 1),
        }


class Sim:
    def __init__(
        self,
        our_id: int,
        opp_id: int,
        n_games: int,
        our_stat: Stat | None = None,
        opp_stat: Stat | None = None,
        our_events: pd.DataFrame | None = None,
        opp_events: pd.DataFrame | None = None,
    ):
        self.our_id = our_id
        self.opp_id = opp_id
        self.n_games = n_games
        self.our_events = our_events if our_events is not None else match_events(our_id, n_games, include_opponent=True, spadl=True)
        self.opp_events = opp_events if opp_events is not None else match_events(opp_id, n_games, include_opponent=True, spadl=True)
        self.our = our_stat if our_stat is not None else StatBox(self.our_events, our_id).box()
        self.opp = opp_stat if opp_stat is not None else StatBox(self.opp_events, opp_id).box()
        self.state = SimState(
            xg_for=self.our.xg_for_pg,
            xg_against=self.our.xg_against_pg,
            pass_for=self.our.pass_for,
            pass_against=self.opp.pass_for,
            poss=self.our.poss,
        )
        self.rules: List[Rule] = list(RULES)
        self.rule_keys = [rule.data(self.state).get("key") for rule in self.rules]
        self.rule_map = {key: rule for key, rule in zip(self.rule_keys, self.rules) if key}

    def _avg(self) -> tuple[float, float]:
        lam_for = (self.our.xg_for_pg + self.opp.xg_against_pg) / 2
        lam_against = (self.our.xg_against_pg + self.opp.xg_for_pg) / 2
        lam_for = max(0.2, lam_for)
        lam_against = max(0.2, lam_against)
        return lam_for, lam_against

    def _factor(self, lam_for: float, lam_against: float, rules: List[Rule]) -> tuple[float, float]:
        factors = {
            "press_hub": (1.02, 0.92),
            "counter_setpiece": (1.01, 0.95),
            "exploit_pattern": (1.05, 0.98),
        }
        for rule in rules:
            key = rule.data(self.state).get("key")
            if key in factors:
                up, down = factors[key]
                lam_for *= up
                lam_against *= down
        return lam_for, lam_against

    # 기본 승부 확률
    def base(self) -> Dict[str, float]:
        lam_for, lam_against = self._avg()
        return Prob(lam_for, lam_against).out()

    # 전술 적용 확률
    def opt(self) -> Dict[str, float]:
        lam_for, lam_against = self._avg()
        lam_for, lam_against = self._factor(lam_for, lam_against, self.rules)
        return Prob(lam_for, lam_against).out()

    def case(self, scenario: str) -> Dict:
        base_prob = self.base()
        if scenario == "all_tactics":
            label = "종합 전술 적용"
            desc = "모든 분석 기반 전술 동시 적용"
            rule_list = self.rules
        else:
            rule = self.rule_map.get(scenario)
            entry = rule.data(self.state) if rule else None
            label = entry.get("scenario", {}).get("name") if entry else "종합 전술 적용"
            desc = entry.get("scenario", {}).get("description") if entry else "모든 분석 기반 전술 동시 적용"
            rule_list = [rule] if rule else self.rules
        lam_for, lam_against = self._avg()
        lam_for, lam_against = self._factor(lam_for, lam_against, rule_list)
        new_prob = Prob(lam_for, lam_against).out()
        return {
            "scenario": label,
            "description": desc,
            "before": base_prob,
            "after": new_prob,
            "win_change": round(num(new_prob["win"] - base_prob["win"]), 1),
            "recommendation": self.memo(base_prob, new_prob),
        }

    def memo(self, before: Dict, after: Dict) -> str:
        win_change = after["win"] - before["win"]
        if win_change >= 10:
            return "✅ 강력 추천: 이 전술 조합으로 승률이 크게 상승합니다."
        if win_change >= 5:
            return "👍 추천: 전술 적용 시 승률 개선이 예상됩니다."
        if win_change >= 0:
            return "ℹ️ 참고: 소폭의 승률 개선이 가능합니다."
        return "⚠️ 주의: 이 전술은 현재 상황에 적합하지 않을 수 있습니다."

    def hint(self) -> List[Dict]:
        tips: List[Dict] = []
        if self.opp.pass_for > 0.78:
            tips.append({
                "priority": 1,
                "tactic": "중원 압박 강화",
                "reason": f"상대 패스 성공률 {self.opp.pass_for * 100:.0f}%",
                "expected_effect": "빌드업 차단으로 실점 기대치 감소",
                "win_prob_change": "+5%p",
            })
        if self.opp.xg_for_pg > 1.25:
            tips.append({
                "priority": 2,
                "tactic": "수비 라인 낮추기",
                "reason": f"상대 경기당 xG {self.opp.xg_for_pg:.2f}",
                "expected_effect": "박스 침투 억제",
                "win_prob_change": "+3%p",
            })
        if self.our.xg_for_pg < 1.05:
            tips.append({
                "priority": 3,
                "tactic": "역습 집중 전술",
                "reason": f"우리 경기당 xG {self.our.xg_for_pg:.2f}",
                "expected_effect": "전환 공격 효율 개선",
                "win_prob_change": "+4%p",
            })
        if not tips:
            tips.append({
                "priority": 1,
                "tactic": "균형 잡힌 전술 유지",
                "reason": "양팀 기대 득실 균형",
                "expected_effect": "안정적인 경기 운영",
                "win_prob_change": "±0%p",
            })
        return sorted(tips, key=lambda x: x["priority"])


# 프리매치 결과 생성
def prematch(our_events: pd.DataFrame, opponent_events: pd.DataFrame) -> Dict:
    if our_events.empty or opponent_events.empty:
        return {
            "base_prediction": {"win": 0.0, "draw": 0.0, "lose": 0.0},
            "optimal_prediction": {"win": 0.0, "draw": 0.0, "lose": 0.0},
            "win_improvement": 0.0,
            "tactical_suggestions": [],
            "scenarios": [],
        }
    our_id = int(our_events["team_id"].iloc[0])
    opp_id = int(opponent_events["team_id"].iloc[0])
    n_games = int(max(our_events["game_id"].nunique(), opponent_events["game_id"].nunique(), 1))
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_our = pool.submit(StatBox(our_events, our_id).box)
        fut_opp = pool.submit(StatBox(opponent_events, opp_id).box)
        our_stat = fut_our.result()
        opp_stat = fut_opp.result()
    sim = Sim(our_id, opp_id, n_games, our_stat=our_stat, opp_stat=opp_stat, our_events=our_events, opp_events=opponent_events)
    base_prob = sim.base()
    opt_prob = sim.opt()
    scenarios = [sim.case(s) for s in sim.rule_keys + ["all_tactics"]]
    return {
        "base_prediction": base_prob,
        "optimal_prediction": opt_prob,
        "win_improvement": round(num(opt_prob["win"] - base_prob["win"]), 1),
        "tactical_suggestions": sim.hint(),
        "scenarios": scenarios,
    }
