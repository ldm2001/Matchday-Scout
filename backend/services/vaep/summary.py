# VAEP 요약 래퍼 - 특정 팀 기반의 전체 출전 선수 VAEP 통계 조회 유틸리티
import pandas as pd
from typing import Dict, Optional
from .model import team_sum as _team_sum


# 파편화된 호출을 한데 묶어 팀 ID 기반 VAEP 요약 통계를 간편히 쿼리하는 파사드
def team_sum(events_df: pd.DataFrame, team_id: Optional[int] = None, n_top: int = 10) -> Dict:
    # 파라미터로 팀 ID가 안 넘어왔다면 데이터프레임 안에서 주력 팀 하나를 추출해 베이스라인으로 잡음
    if team_id is None:
        team_ids = events_df["team_id"].dropna().unique().tolist() if "team_id" in events_df.columns else []
        team_id = int(team_ids[0]) if team_ids else 0
    # underlying model 함수로 최종 토스
    return _team_sum(events_df, team_id, n_top)
