from __future__ import annotations

from typing import Dict, Iterable, Optional, Set

import pandas as pd
import numpy as np

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0


# SPADL action map
SPADL_ACTION_MAP: Dict[str, Optional[str]] = {
    "Pass": "pass",
    "Pass_Corner": "corner_crossed",
    "Pass_Freekick": "freekick_crossed",
    "Cross": "cross",
    "Throw-In": "throw_in",
    "Goal Kick": "goal_kick",
    "Carry": "dribble",
    "Take-On": "take_on",
    "Shot": "shot",
    "Goal": "shot",
    "Foul": "foul",
    "Handball_Foul": "foul",
    "Tackle": "tackle",
    "Interception": "interception",
    "Intervention": "interception",
    "Recovery": "interception",
    "Clearance": "clearance",
    "Aerial Clearance": "clearance",
    "Block": "block",
    "Duel": "duel",
    "Catch": "keeper_claim",
    "Parry": "keeper_save",
    "Hit": "keeper_punch",
    "Error": "error",
    # Non-actions or annotations that should be dropped
    "Pass Received": None,
    "Ball Received": None,
    "Pause": None,
    "Defensive Line Support": None,
    "Out": None,
    "Offside": None,
}

SPADL_RESULT_MAP: Dict[str, str] = {
    "Successful": "success",
    "Unsuccessful": "fail",
    "Off Target": "offtarget",
    "On Target": "ontarget",
    "Blocked": "blocked",
    "Goal": "goal",
    "Yellow_Card": "yellow_card",
    "Direct_Red_Card": "red_card",
    "Second_Yellow_Card": "red_card",
    "Own Goal": "owngoal",
}


def _num(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        f = float(value)
        if np.isnan(f) or np.isinf(f):
            return default
        return f
    except Exception:
        return default


# Team-side flip for away games
def team_norm(
    events: pd.DataFrame, team_id: int, matches: pd.DataFrame
) -> pd.DataFrame:
    events = events.copy()
    if events.empty:
        return events

    away_games: Set[int] = set(
        matches.loc[matches["away_team_id"] == team_id, "game_id"].astype(int).tolist()
    )
    if not away_games:
        return events

    mask = events["game_id"].isin(away_games)
    if not mask.any():
        return events

    for col in ("start_x", "end_x"):
        if col in events.columns:
            events.loc[mask, col] = PITCH_LENGTH - events.loc[mask, col].astype(float)
    for col in ("start_y", "end_y"):
        if col in events.columns:
            events.loc[mask, col] = PITCH_WIDTH - events.loc[mask, col].astype(float)
    if "dx" in events.columns:
        events.loc[mask, "dx"] = -events.loc[mask, "dx"].astype(float)
    if "dy" in events.columns:
        events.loc[mask, "dy"] = -events.loc[mask, "dy"].astype(float)

    return events


# Away-team flip for both sides
def side_norm(events: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    events = events.copy()
    if events.empty:
        return events

    away_map = matches.set_index("game_id")["away_team_id"].to_dict()
    away_ids = events["game_id"].map(away_map)
    mask = events["team_id"] == away_ids
    if not mask.any():
        return events

    for col in ("start_x", "end_x"):
        if col in events.columns:
            events.loc[mask, col] = PITCH_LENGTH - pd.to_numeric(events.loc[mask, col], errors="coerce").fillna(0)
    for col in ("start_y", "end_y"):
        if col in events.columns:
            events.loc[mask, col] = PITCH_WIDTH - pd.to_numeric(events.loc[mask, col], errors="coerce").fillna(0)
    if "dx" in events.columns:
        events.loc[mask, "dx"] = -pd.to_numeric(events.loc[mask, "dx"], errors="coerce").fillna(0)
    if "dy" in events.columns:
        events.loc[mask, "dy"] = -pd.to_numeric(events.loc[mask, "dy"], errors="coerce").fillna(0)

    return events


# SPADL-like fields
def spadl_map(events: pd.DataFrame) -> pd.DataFrame:
    events = events.copy()
    if events.empty:
        return events

    def action_map(t: object) -> Optional[str]:
        key = str(t) if t is not None else ""
        return SPADL_ACTION_MAP.get(key, "other")

    def result_map(r: object) -> str:
        key = str(r) if r is not None else ""
        return SPADL_RESULT_MAP.get(key, "unknown")

    events["spadl_type"] = events["type_name"].apply(action_map)
    events["spadl_result"] = events["result_name"].apply(result_map)
    subtype_col = None
    for col in ("subtype_name", "pass_subtype", "pass_subtype_name", "sub_type", "sub_type_name"):
        if col in events.columns:
            subtype_col = col
            break
    if subtype_col:
        events["spadl_subtype"] = events[subtype_col].fillna("unknown").astype(str)
    else:
        events["spadl_subtype"] = events["type_name"].fillna("unknown").astype(str)
    body_col = None
    for col in ("body_part", "body_part_name", "body_part_type", "body_part_name_en"):
        if col in events.columns:
            body_col = col
            break
    if body_col:
        events["spadl_body_part"] = events[body_col].fillna("unknown").astype(str)
    else:
        events["spadl_body_part"] = "unknown"
    events["is_action"] = events["spadl_type"].notna()
    return events


# Action rows only
def action_rows(events: pd.DataFrame) -> pd.DataFrame:
    if "spadl_type" not in events.columns:
        events = spadl_map(events)
    return events[events["spadl_type"].notna()].copy()


def goal_flag(event: pd.Series) -> bool:
    t = str(event.get("type_name", ""))
    r = str(event.get("result_name", ""))
    return t == "Goal" or r == "Goal"


def goal_dist(x: float, y: float) -> float:
    x = _num(x, PITCH_LENGTH / 2)
    y = _num(y, PITCH_WIDTH / 2)
    return float(np.hypot(PITCH_LENGTH - x, (PITCH_WIDTH / 2) - y))


def goal_angle(x: float, y: float) -> float:
    x = _num(x, PITCH_LENGTH / 2)
    y = _num(y, PITCH_WIDTH / 2)
    dx = PITCH_LENGTH - x
    dy = abs((PITCH_WIDTH / 2) - y)
    goal_width = 7.32
    denom = (dx * dx + dy * dy) - (goal_width / 2) ** 2
    if denom <= 0:
        return float(np.pi)
    return float(np.arctan2(goal_width * dx, denom))
