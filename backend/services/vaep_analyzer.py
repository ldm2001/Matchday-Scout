# VAEP summary wrapper
import pandas as pd
from typing import Dict, Optional
from .vaep_model import team_sum as _team_sum


def team_sum(events_df: pd.DataFrame, team_id: Optional[int] = None, n_top: int = 10) -> Dict:
    if team_id is None:
        team_ids = events_df["team_id"].dropna().unique().tolist() if "team_id" in events_df.columns else []
        team_id = int(team_ids[0]) if team_ids else 0
    return _team_sum(events_df, team_id, n_top)
