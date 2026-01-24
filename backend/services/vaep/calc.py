# VAEP calculator wrapper
import pandas as pd
from typing import Dict, List, Optional
from ..core.data import matches
from .model import prob_vals, vaep_vals, team_vals
from ..core.spadl import spadl_map, action_rows

class VAEPCalculator:
    def __init__(self, events_df: pd.DataFrame):
        self.events = events_df.copy()

    def action_vals(self) -> pd.DataFrame:
        events = spadl_map(self.events)
        events = action_rows(events)
        match_df = matches()[["game_id", "game_date"]].copy()
        match_df["game_date"] = pd.to_datetime(match_df["game_date"], errors="coerce")
        game_dates = match_df.set_index("game_id")["game_date"].to_dict()
        drop_games = sorted(events["game_id"].dropna().astype(int).unique().tolist())
        dates = [game_dates.get(gid) for gid in drop_games if pd.notna(game_dates.get(gid))]
        date_max = min(dates) - pd.Timedelta(seconds=1) if dates else None
        p_score, p_concede, _ = prob_vals(events, date_max=date_max, drop_games=drop_games)
        if len(p_score) == 0:
            return events
        return vaep_vals(events, p_score, p_concede)

    def player_ranks(self, team_id: Optional[int] = None) -> List[Dict]:
        values = self.action_vals()
        if values.empty:
            return []
        if team_id is not None:
            values = values[values["team_id"] == team_id]
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
        grouped.columns = [
            "player_id",
            "player_name",
            "total_vaep",
            "offensive_vaep",
            "defensive_vaep",
            "actions",
        ]
        grouped["vaep_per_90"] = grouped["total_vaep"] / grouped["actions"].clip(lower=1) * 100
        return grouped.sort_values("total_vaep", ascending=False).to_dict("records")


def team_sum(events_df: pd.DataFrame, team_id: int, n_top: int = 10) -> Dict:
    return team_vals(events_df, team_id, n_top_actions=n_top)
