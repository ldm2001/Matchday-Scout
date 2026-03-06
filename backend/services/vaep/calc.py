# VAEP(Valuing Actions by Estimating Probabilities) 지표 계산기 래퍼 클래스
import pandas as pd
from typing import Dict, List, Optional
from ..core.data import matches
from .model import prob_vals, vaep_vals, team_vals
from ..core.spadl import spadl_map, action_rows

# 원본 이벤트 포맷을 받아 VAEP 로직을 돌리기 좋게 파이프라인을 엮어주는 클래스
class VAEPCalculator:
    def __init__(self, events_df: pd.DataFrame):
        # 방어적 복사본 유지
        self.events = events_df.copy()

    # 액션 단위의 VAEP(공격+수비 기여도) 밸류를 산출하는 메인 함수
    def action_vals(self) -> pd.DataFrame:
        # 1) 오픈트랙 스키마를 SPADL 표준 체계로 매핑
        events = spadl_map(self.events)
        # 2) 무의미한 비행동(Non-action) 로우들 제거
        events = action_rows(events)
        
        # 경기 메타데이터 로드 및 날짜 파싱 (과거 가중치용)
        match_df = matches()[["game_id", "game_date"]].copy()
        match_df["game_date"] = pd.to_datetime(match_df["game_date"], errors="coerce")
        game_dates = match_df.set_index("game_id")["game_date"].to_dict()
        
        # 미래 데이터 방지: 들어온 이벤트들의 경기 날짜들 중 가장 옛날 날짜 추출
        drop_games = sorted(events["game_id"].dropna().astype(int).unique().tolist())
        dates = [game_dates.get(gid) for gid in drop_games if pd.notna(game_dates.get(gid))]
        date_max = min(dates) - pd.Timedelta(seconds=1) if dates else None
        
        # 3) 머신러닝 스코어링 모델 점수 추론 
        p_score, p_concede, _ = prob_vals(events, date_max=date_max, drop_games=drop_games)
        if len(p_score) == 0:
            return events
            
        # 4) 이전 상태 대비 득실 확률 증감을 최종 VAEP 값으로 연산하여 병합 반환
        return vaep_vals(events, p_score, p_concede)

    # 산출된 VAEP 액션 테이블을 바탕으로, 선수별 누적 기여도 랭킹 산출
    def player_ranks(self, team_id: Optional[int] = None) -> List[Dict]:
        values = self.action_vals()
        if values.empty:
            return []
            
        # 특정 팀으로 클리핑
        if team_id is not None:
            values = values[values["team_id"] == team_id]
            
        # 선수 단위로 그룹바이 후 공격/수비 VAEP, 액션빈도 총합 집계
        grouped = (
            values.groupby(["player_id", "player_name_ko"], dropna=False)[
                ["vaep_total", "vaep_offensive", "vaep_defensive", "action_id"]
            ]
            .agg(
                {
                    "vaep_total": "sum",
                    "vaep_offensive": "sum",
                    "vaep_defensive": "sum",
                    "action_id": "count",
                }
            )
            .reset_index()
        )
        # 클라이언트 제공용 컬럼명 리네이밍
        grouped.columns = [
            "player_id",
            "player_name",
            "total_vaep",
            "offensive_vaep",
            "defensive_vaep",
            "actions",
        ]
        # 90분(평균 액션 단위 보정) 당 기여도 페이스 산출
        grouped["vaep_per_90"] = grouped["total_vaep"] / grouped["actions"].clip(lower=1) * 100
        # 총합 VAEP 1위부터 줄세워서 DTO 반환
        return grouped.sort_values("total_vaep", ascending=False).to_dict("records")


# 특정 팀 전체 기여도 요약을 제공하는 헬퍼 함수
def team_sum(events_df: pd.DataFrame, team_id: int, n_top: int = 10) -> Dict:
    return team_vals(events_df, team_id, n_top_actions=n_top)
