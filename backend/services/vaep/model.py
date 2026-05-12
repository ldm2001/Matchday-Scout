# 축구 액션마다 득실 확률을 계산해 선수 가치를 매기는 VAEP 모델
from __future__ import annotations

# 표준 라이브러리
import hashlib
import logging
import pickle
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# 외부 라이브러리
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score

# 같은 프로젝트 모듈
from ..core.data import data_stamp, match_events, matches, raw
from ..core.spadl import (
    action_rows,
    goal_angle,
    goal_dist,
    goal_flag,
    side_norm,
    spadl_map,
)

# sklearn 1.6+는 prefit 대신 FrozenEstimator 사용
try:
    from sklearn.frozen import FrozenEstimator
    _HAS_FROZEN = True
except ImportError:
    FrozenEstimator = None
    _HAS_FROZEN = False

# CatBoost에 sklearn 신버전용 태그 메서드 추가한 래퍼
if _HAS_FROZEN:
    from sklearn.utils._tags import ClassifierTags, InputTags, TargetTags, Tags

    class _CatBoostShim(CatBoostClassifier):
        def __sklearn_tags__(self):
            return Tags(
                estimator_type="classifier",
                target_tags=TargetTags(required=True),
                classifier_tags=ClassifierTags(),
                input_tags=InputTags(allow_nan=True),
                transformer_tags=None,
                regressor_tags=None,
            )
else:
    _CatBoostShim = CatBoostClassifier

K_ACTIONS = 10

@dataclass
class VaepModels:
    scoring_model: object
    conceding_model: object
    feature_columns: List[str]
    metrics: Dict[str, float]


_MODEL_CACHE: Dict[Tuple[Optional[pd.Timestamp], Tuple[int, ...]], VaepModels] = {}
_MODEL_MARK: Optional[tuple] = None

# 학습된 모델 저장 폴더 서버 재시작해도 유지
_DISK_CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "vaep"
_LOG = logging.getLogger(__name__)

# 데이터 스탬프 옵션으로 캐시 파일 경로 생성
def _disk_cache_path(mark: tuple, date_key, drop_key: tuple) -> Path:
    mark_hash = hashlib.sha1(repr(mark).encode()).hexdigest()[:12]
    key_hash = hashlib.sha1(repr((date_key, drop_key)).encode()).hexdigest()[:12]
    return _DISK_CACHE_DIR / f"vaep_{mark_hash}_{key_hash}.pkl"

# 데이터 바뀌면 이전 캐시 삭제
def _purge_disk_cache(current_mark: tuple) -> None:
    if not _DISK_CACHE_DIR.exists():
        return
    current = hashlib.sha1(repr(current_mark).encode()).hexdigest()[:12]
    for path in _DISK_CACHE_DIR.glob("vaep_*.pkl"):
        parts = path.stem.split("_")
        if len(parts) >= 3 and parts[1] != current:
            try:
                path.unlink()
            except OSError:
                pass

# 디스크 캐시에서 모델 로드
def _load_disk(mark: tuple, date_key, drop_key: tuple) -> Optional[VaepModels]:
    path = _disk_cache_path(mark, date_key, drop_key)
    if not path.exists():
        return None
    try:
        with path.open("rb") as f:
            obj = pickle.load(f)
        if isinstance(obj, VaepModels):
            _LOG.info("VAEP 디스크 캐시 적중: %s", path.name)
            return obj
        return None
    except Exception as exc:
        _LOG.warning("VAEP 디스크 캐시 로드 실패 (%s): %s", path.name, exc)
        try:
            path.unlink()
        except OSError:
            pass
        return None


# 학습된 모델 디스크에 저장
def _save_disk(mark: tuple, date_key, drop_key: tuple, models: VaepModels) -> None:
    try:
        _DISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _disk_cache_path(mark, date_key, drop_key)
        tmp = path.with_suffix(".pkl.tmp")
        with tmp.open("wb") as f:
            pickle.dump(models, f, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(path)
        _LOG.info("VAEP 디스크 캐시 저장: %s", path.name)
    except Exception as exc:
        _LOG.warning("VAEP 디스크 캐시 저장 실패: %s", exc)


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

def _goal_team(event: pd.Series, teams: List[int]) -> Optional[int]:
    if not goal_flag(event):
        return None
    team_id = int(event.get("team_id"))
    result = str(event.get("result_name", ""))
    if result == "Own Goal" and len(teams) == 2:
        return teams[0] if team_id == teams[1] else teams[1]
    return team_id

def _game_seq(events: pd.DataFrame) -> pd.DataFrame:
    return events.sort_values(["game_id", "period_id", "time_seconds", "action_id"]).reset_index(drop=True)

# 학습용 피처 묶음 만들기
def _feat_pack(
    events: pd.DataFrame, k_actions: int = K_ACTIONS
) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray, pd.DataFrame]:
    events = _game_seq(events)
    features: List[Dict[str, object]] = []
    labels_score: List[int] = []
    labels_concede: List[int] = []
    meta_rows: List[Dict[str, object]] = []

    for game_id in events["game_id"].unique():
        game = events[events["game_id"] == game_id].reset_index(drop=True)
        if game.empty:
            continue

        teams = sorted(game["team_id"].dropna().unique().astype(int).tolist())
        team_a = teams[0] if teams else None
        team_b = teams[1] if len(teams) > 1 else None

        n = len(game)
        types = game["spadl_type"].fillna("other").astype(str).tolist()
        results = game["spadl_result"].fillna("unknown").astype(str).tolist()
        body_parts = game["spadl_body_part"].fillna("unknown").astype(str).tolist()
        subtypes = (
            game["spadl_subtype"].fillna("unknown").astype(str).tolist()
            if "spadl_subtype" in game.columns
            else ["unknown"] * n
        )

        start_x = pd.to_numeric(game.get("start_x", 0), errors="coerce").fillna(0).to_numpy()
        start_y = pd.to_numeric(game.get("start_y", 0), errors="coerce").fillna(0).to_numpy()
        end_x = pd.to_numeric(game.get("end_x", 0), errors="coerce").fillna(0).to_numpy()
        end_y = pd.to_numeric(game.get("end_y", 0), errors="coerce").fillna(0).to_numpy()
        dx = pd.to_numeric(game.get("dx", 0), errors="coerce").fillna(0).to_numpy()
        dy = pd.to_numeric(game.get("dy", 0), errors="coerce").fillna(0).to_numpy()
        time_seconds = pd.to_numeric(game.get("time_seconds", 0), errors="coerce").fillna(0).to_numpy()
        period_id = pd.to_numeric(game.get("period_id", 0), errors="coerce").fillna(1).to_numpy()
        period_id = np.where(period_id <= 0, 1, period_id)
        time_abs = time_seconds + (period_id - 1) * 2700.0
        team_ids = pd.to_numeric(game.get("team_id", 0), errors="coerce").fillna(0).astype(int).to_numpy()

        dist = np.hypot(dx, dy)
        dist_to_goal_start = np.array([goal_dist(x, y) for x, y in zip(start_x, start_y)])
        dist_to_goal_end = np.array([goal_dist(x, y) for x, y in zip(end_x, end_y)])
        angle_to_goal_end = np.array([goal_angle(x, y) for x, y in zip(end_x, end_y)])

        goal_team = [None] * n
        for i in range(n):
            goal_team[i] = _goal_team(game.iloc[i], teams)
        for i in range(1, n):
            if str(game.iloc[i].get("type_name", "")) == "Goal":
                prev = game.iloc[i - 1]
                if str(prev.get("type_name", "")) == "Shot" and str(prev.get("result_name", "")) in {"Goal", "Own Goal"}:
                    goal_team[i] = None

        score_a = 0
        score_b = 0
        score_for = np.zeros(n)
        score_against = np.zeros(n)
        score_diff = np.zeros(n)
        time_since_prev = np.zeros(n)
        possession_change = np.zeros(n)

        prev_time = None
        prev_team = None
        for i in range(n):
            team = team_ids[i]
            if team_a is None:
                team_a = team
            if team_b is None and team != team_a:
                team_b = team

            if goal_team[i] is not None:
                if goal_team[i] == team_a:
                    score_a += 1
                elif team_b is not None and goal_team[i] == team_b:
                    score_b += 1

            if team == team_a:
                score_for[i] = score_a
                score_against[i] = score_b if team_b is not None else 0
            else:
                score_for[i] = score_b if team_b is not None else 0
                score_against[i] = score_a
            score_diff[i] = score_for[i] - score_against[i]

            if prev_time is None:
                time_since_prev[i] = 0
            else:
                time_since_prev[i] = max(0.0, time_abs[i] - prev_time)

            if prev_team is None:
                possession_change[i] = 0
            else:
                possession_change[i] = 1 if team != prev_team else 0

            prev_time = time_abs[i]
            prev_team = team

        for i in range(n):
            # 다음 k개 액션 안에서 득점/실점 발생 여부 라벨링
            score_label = 0
            concede_label = 0
            team = team_ids[i]
            for j in range(i + 1, min(i + k_actions + 1, n)):
                if goal_team[j] is None:
                    continue
                if goal_team[j] == team:
                    score_label = 1
                else:
                    concede_label = 1
                if score_label and concede_label:
                    break

            f: Dict[str, object] = {}
            for offset, prefix in zip([-4, -3, -2, -1, 0], ["a0", "a1", "a2", "a3", "a4"]):
                idx = i + offset
                if idx < 0:
                    f[f"{prefix}_type"] = "none"
                    f[f"{prefix}_result"] = "none"
                    f[f"{prefix}_body"] = "none"
                    f[f"{prefix}_subtype"] = "none"
                    f[f"{prefix}_start_x"] = 0.0
                    f[f"{prefix}_start_y"] = 0.0
                    f[f"{prefix}_end_x"] = 0.0
                    f[f"{prefix}_end_y"] = 0.0
                    f[f"{prefix}_dx"] = 0.0
                    f[f"{prefix}_dy"] = 0.0
                    f[f"{prefix}_dist"] = 0.0
                    f[f"{prefix}_dist_goal_start"] = 0.0
                    f[f"{prefix}_dist_goal_end"] = 0.0
                    f[f"{prefix}_angle_goal_end"] = 0.0
                    f[f"{prefix}_time_norm"] = 0.0
                    f[f"{prefix}_period"] = 0.0
                else:
                    f[f"{prefix}_type"] = types[idx]
                    f[f"{prefix}_result"] = results[idx]
                    f[f"{prefix}_body"] = body_parts[idx]
                    f[f"{prefix}_subtype"] = subtypes[idx]
                    f[f"{prefix}_start_x"] = float(start_x[idx])
                    f[f"{prefix}_start_y"] = float(start_y[idx])
                    f[f"{prefix}_end_x"] = float(end_x[idx])
                    f[f"{prefix}_end_y"] = float(end_y[idx])
                    f[f"{prefix}_dx"] = float(dx[idx])
                    f[f"{prefix}_dy"] = float(dy[idx])
                    f[f"{prefix}_dist"] = float(dist[idx])
                    f[f"{prefix}_dist_goal_start"] = float(dist_to_goal_start[idx])
                    f[f"{prefix}_dist_goal_end"] = float(dist_to_goal_end[idx])
                    f[f"{prefix}_angle_goal_end"] = float(angle_to_goal_end[idx])
                    f[f"{prefix}_time_norm"] = float(time_abs[idx] / 5400.0)
                    f[f"{prefix}_period"] = float(period_id[idx])

            # 현재 경기 상황 피처
            f["time_since_prev"] = float(time_since_prev[i])
            f["possession_change"] = float(possession_change[i])
            f["score_for"] = float(score_for[i])
            f["score_against"] = float(score_against[i])
            f["score_diff"] = float(score_diff[i])

            features.append(f)
            labels_score.append(score_label)
            labels_concede.append(concede_label)
            meta_rows.append(
                {
                    "game_id": int(game.iloc[i]["game_id"]),
                    "action_id": int(game.iloc[i]["action_id"]),
                    "team_id": int(game.iloc[i]["team_id"]),
                    "player_id": game.iloc[i].get("player_id"),
                }
            )

    features_df = pd.DataFrame(features)
    labels_score_arr = np.array(labels_score, dtype=int)
    labels_concede_arr = np.array(labels_concede, dtype=int)
    meta_df = pd.DataFrame(meta_rows)
    return features_df, labels_score_arr, labels_concede_arr, meta_df

# CatBoost 학습 후 확률 보정 적용
def _model_cal(
    X_train: pd.DataFrame, y_train: np.ndarray, X_val: pd.DataFrame, y_val: np.ndarray
) -> CalibratedClassifierCV:
    categorical_cols = [
        c for c in X_train.columns if c.endswith(("_type", "_result", "_body", "_subtype"))
    ]

    X_train = X_train.copy()
    X_val = X_val.copy()
    for col in categorical_cols:
        X_train[col] = X_train[col].fillna("unknown").astype(str)
        X_val[col] = X_val[col].fillna("unknown").astype(str)
    cat_idx = [X_train.columns.get_loc(c) for c in categorical_cols]
    base = _CatBoostShim(
        iterations=400,
        depth=6,
        learning_rate=0.1,
        loss_function="Logloss",
        eval_metric="AUC",
        random_seed=42,
        verbose=False,
        allow_writing_files=False,
    )
    base.fit(X_train, y_train, cat_features=cat_idx, eval_set=(X_val, y_val), verbose=False)

    # 양성 샘플 50개 이상이면 isotonic 아니면 sigmoid 보정
    method = "isotonic" if y_val.sum() >= 50 else "sigmoid"
    # sklearn 버전 호환 분기
    if _HAS_FROZEN:
        calibrated = CalibratedClassifierCV(FrozenEstimator(base), method=method)
    else:
        calibrated = CalibratedClassifierCV(base, method=method, cv="prefit")
    calibrated.fit(X_val, y_val)
    return calibrated

# 캐시 있으면 재사용 없으면 새로 학습
def vaep_models(
    date_max: Optional[pd.Timestamp] = None, drop_games: Optional[Iterable[int]] = None
) -> VaepModels:
    global _MODEL_MARK
    mark = data_stamp()
    if _MODEL_MARK != mark:
        _MODEL_CACHE.clear()
        _MODEL_MARK = mark
        _purge_disk_cache(mark)

    date_key = pd.to_datetime(date_max) if date_max is not None else None
    if drop_games:
        drop_key = tuple(sorted({int(g) for g in drop_games if g is not None and not pd.isna(g)}))
    else:
        drop_key = ()
    key = (date_key, drop_key)
    if key in _MODEL_CACHE:
        return _MODEL_CACHE[key]

    # 메모리 캐시 미스면 디스크 캐시 확인 후 학습 비용 회피
    disk_models = _load_disk(mark, date_key, drop_key)
    if disk_models is not None:
        _MODEL_CACHE[key] = disk_models
        return disk_models

    match_df = matches()[["game_id", "game_date"]].copy()
    match_df["game_date"] = pd.to_datetime(match_df["game_date"], errors="coerce")
    if date_key is not None:
        match_df = match_df[match_df["game_date"] <= date_key]
    if drop_key:
        match_df = match_df[~match_df["game_id"].isin(drop_key)]
    if match_df.empty and date_key is not None:
        date_key = None
        key = (date_key, drop_key)
        if key in _MODEL_CACHE:
            return _MODEL_CACHE[key]
        match_df = matches()[["game_id", "game_date"]].copy()
        match_df["game_date"] = pd.to_datetime(match_df["game_date"], errors="coerce")
        if drop_key:
            match_df = match_df[~match_df["game_id"].isin(drop_key)]

    events = raw()
    if date_key is not None or drop_key:
        allowed_games = set(match_df["game_id"].astype(int).tolist())
        events = events[events["game_id"].isin(allowed_games)]

    events = side_norm(events, matches())
    events = spadl_map(events)
    events = action_rows(events)

    features, y_score, y_concede, meta = _feat_pack(events, k_actions=K_ACTIONS)
    if features.empty:
        raise ValueError("No features available for VAEP training")

    game_dates = match_df.set_index("game_id")["game_date"].to_dict()
    meta["game_date"] = meta["game_id"].map(game_dates)

    # 미래 정보 누수 방지 위해 경기 날짜로 train/val 분할
    unique_games = meta[["game_id", "game_date"]].drop_duplicates()
    dated_games = unique_games.dropna(subset=["game_date"]).sort_values("game_date", ascending=True)
    if len(dated_games) >= 2:
        split_games = dated_games
    elif len(unique_games) >= 2:
        split_games = unique_games.sort_values("game_id", ascending=True)
    else:
        split_games = None

    if split_games is None:
        split_idx = int(len(meta) * 0.8)
        split_idx = max(1, min(len(meta) - 1, split_idx))
        train_mask = pd.Series(range(len(meta))) < split_idx
        val_mask = ~train_mask
    else:
        split_idx = int(len(split_games) * 0.8)
        split_idx = max(1, min(len(split_games) - 1, split_idx))
        train_games = set(split_games.iloc[:split_idx]["game_id"].tolist())
        val_games = set(split_games.iloc[split_idx:]["game_id"].tolist())
        train_mask = meta["game_id"].isin(train_games)
        val_mask = meta["game_id"].isin(val_games)

    X_train = features[train_mask]
    X_val = features[val_mask]
    y_score_train = y_score[train_mask.values]
    y_score_val = y_score[val_mask.values]
    y_concede_train = y_concede[train_mask.values]
    y_concede_val = y_concede[val_mask.values]

    scoring_model = _model_cal(X_train, y_score_train, X_val, y_score_val)
    conceding_model = _model_cal(X_train, y_concede_train, X_val, y_concede_val)

    p_score_val = scoring_model.predict_proba(X_val)[:, 1]
    p_concede_val = conceding_model.predict_proba(X_val)[:, 1]

    score_base_rate = float(y_score_val.mean()) if len(y_score_val) else 0.0
    concede_base_rate = float(y_concede_val.mean()) if len(y_concede_val) else 0.0
    score_baseline_acc = max(score_base_rate, 1 - score_base_rate)
    concede_baseline_acc = max(concede_base_rate, 1 - concede_base_rate)

    metrics = {
        "score_accuracy": float(accuracy_score(y_score_val, p_score_val >= 0.5)),
        "concede_accuracy": float(accuracy_score(y_concede_val, p_concede_val >= 0.5)),
        "score_brier": float(brier_score_loss(y_score_val, p_score_val)),
        "concede_brier": float(brier_score_loss(y_concede_val, p_concede_val)),
        "score_auc": float(roc_auc_score(y_score_val, p_score_val)) if len(np.unique(y_score_val)) > 1 else 0.0,
        "concede_auc": float(roc_auc_score(y_concede_val, p_concede_val)) if len(np.unique(y_concede_val)) > 1 else 0.0,
        "score_base_rate": score_base_rate,
        "concede_base_rate": concede_base_rate,
        "score_baseline_accuracy": float(score_baseline_acc),
        "concede_baseline_accuracy": float(concede_baseline_acc),
    }

    _MODEL_CACHE[key] = VaepModels(
        scoring_model=scoring_model,
        conceding_model=conceding_model,
        feature_columns=features.columns.tolist(),
        metrics=metrics,
    )
    _save_disk(mark, date_key, drop_key, _MODEL_CACHE[key])
    return _MODEL_CACHE[key]

def _feat_events(events: pd.DataFrame) -> pd.DataFrame:
    features, _, _, _ = _feat_pack(events, k_actions=K_ACTIONS)
    return features

# 액션마다 득점 실점 확률 예측
def prob_vals(
    events: pd.DataFrame,
    date_max: Optional[pd.Timestamp] = None,
    drop_games: Optional[Iterable[int]] = None,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, float]]:
    models = vaep_models(date_max=date_max, drop_games=drop_games)
    if "spadl_type" not in events.columns:
        events = spadl_map(events)
    events = action_rows(events)
    events = side_norm(events, matches())
    features = _feat_events(events)
    if features.empty:
        return np.array([]), np.array([]), models.metrics
    p_score = models.scoring_model.predict_proba(features)[:, 1]
    p_concede = models.conceding_model.predict_proba(features)[:, 1]
    return p_score, p_concede, models.metrics


# 액션 전후 확률 차이로 선수가 만든 가치 계산
def vaep_vals(
    events: pd.DataFrame, p_score: np.ndarray, p_concede: np.ndarray
) -> pd.DataFrame:
    events = _game_seq(events).copy()
    if len(events) == 0:
        return events

    events["p_score"] = p_score
    events["p_concede"] = p_concede
    events["vaep_offensive"] = 0.0
    events["vaep_defensive"] = 0.0
    events["vaep_total"] = 0.0

    for game_id in events["game_id"].unique():
        mask = events["game_id"] == game_id
        idxs = events.index[mask].tolist()
        prev_team = None
        prev_p_score = 0.0
        prev_p_concede = 0.0

        for idx in idxs:
            team = int(events.at[idx, "team_id"])
            if prev_team is None:
                prev_score_for_team = 0.0
                prev_concede_for_team = 0.0
            elif team == prev_team:
                prev_score_for_team = prev_p_score
                prev_concede_for_team = prev_p_concede
            else:
                # 점유 바뀌면 상대 시점 확률 사용
                prev_score_for_team = prev_p_concede
                prev_concede_for_team = prev_p_score

            curr_score = float(events.at[idx, "p_score"])
            curr_concede = float(events.at[idx, "p_concede"])
            vaep_off = curr_score - prev_score_for_team
            vaep_def = -(curr_concede - prev_concede_for_team)

            events.at[idx, "vaep_offensive"] = vaep_off
            events.at[idx, "vaep_defensive"] = vaep_def
            events.at[idx, "vaep_total"] = vaep_off + vaep_def

            prev_team = team
            prev_p_score = curr_score
            prev_p_concede = curr_concede

    return events

# 액션별 VAEP를 선수별로 합산
def player_vals(events: pd.DataFrame, team_id: Optional[int] = None) -> List[Dict]:
    if team_id is not None:
        events = events[events["team_id"] == team_id]

    grouped = (
        events.groupby(["player_id", "player_name_ko"], dropna=False)[
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
    grouped["avg_vaep"] = grouped["total_vaep"] / grouped["actions"].clip(lower=1)

    grouped["total_vaep"] = grouped["total_vaep"].round(3)
    grouped["offensive_vaep"] = grouped["offensive_vaep"].round(3)
    grouped["defensive_vaep"] = grouped["defensive_vaep"].round(3)
    grouped["avg_vaep"] = grouped["avg_vaep"].round(4)

    return grouped.sort_values("total_vaep", ascending=False).to_dict("records")


# 팀 전체 VAEP와 공수 베스트 선수 반환
def team_sum(events: pd.DataFrame, team_id: int, n_top: int = 10, guard: bool = False) -> Dict:
    events = spadl_map(events)
    events = action_rows(events)
    if guard:
        match_df = matches()[["game_id", "game_date"]].copy()
        match_df["game_date"] = pd.to_datetime(match_df["game_date"], errors="coerce")
        game_dates = match_df.set_index("game_id")["game_date"].to_dict()
        drop_games = sorted(events["game_id"].dropna().astype(int).unique().tolist())
        dates = [game_dates.get(gid) for gid in drop_games if pd.notna(game_dates.get(gid))]
        date_max = min(dates) - pd.Timedelta(seconds=1) if dates else None
        p_score, p_concede, metrics = prob_vals(events, date_max=date_max, drop_games=drop_games)
    else:
        p_score, p_concede, metrics = prob_vals(events)
    if len(p_score) == 0:
        return {
            "team_total_vaep": 0.0,
            "top_players": [],
            "top_offensive": [],
            "top_defensive": [],
            "methodology": "VAEP",
            "metrics": metrics,
        }

    values = vaep_vals(events, p_score, p_concede)
    players = player_vals(values, team_id=team_id)
    team_total = sum(p["total_vaep"] for p in players)

    return {
        "team_total_vaep": round(float(team_total), 3),
        "top_players": players[:n_top],
        "top_offensive": sorted(players, key=lambda x: x["offensive_vaep"], reverse=True)[:5],
        "top_defensive": sorted(players, key=lambda x: x["defensive_vaep"], reverse=True)[:5],
        "methodology": "VAEP",
        "metrics": metrics,
    }

# 팀 내 고가치 액션 상위 추출
def team_vals(events: pd.DataFrame, team_id: int, n_top_actions: int = 5, guard: bool = False) -> Dict:
    events = spadl_map(events)
    events = action_rows(events)
    if guard:
        match_df = matches()[["game_id", "game_date"]].copy()
        match_df["game_date"] = pd.to_datetime(match_df["game_date"], errors="coerce")
        game_dates = match_df.set_index("game_id")["game_date"].to_dict()
        drop_games = sorted(events["game_id"].dropna().astype(int).unique().tolist())
        dates = [game_dates.get(gid) for gid in drop_games if pd.notna(game_dates.get(gid))]
        date_max = min(dates) - pd.Timedelta(seconds=1) if dates else None
        p_score, p_concede, metrics = prob_vals(events, date_max=date_max, drop_games=drop_games)
    else:
        p_score, p_concede, metrics = prob_vals(events)
    if len(p_score) == 0:
        return {
            "team_id": team_id,
            "total_vaep": 0.0,
            "offensive_vaep": 0.0,
            "defensive_vaep": 0.0,
            "player_ranks": [],
            "top_valuable_actions": [],
            "methodology": "VAEP",
            "metrics": metrics,
        }

    values = vaep_vals(events, p_score, p_concede)
    values_team = values[values["team_id"] == team_id]
    ratings = player_vals(values, team_id=team_id)
    top = (
        values_team.nlargest(n_top_actions, "vaep_total")[
            ["player_name_ko", "type_name", "vaep_total", "vaep_offensive", "start_x", "start_y", "end_x", "end_y"]
        ]
        .fillna(0)
    )
    top_actions = []
    for _, row in top.iterrows():
        top_actions.append(
            {
                "player": str(row.get("player_name_ko", "Unknown")),
                "action": str(row.get("type_name", "Unknown")),
                "value": round(float(row.get("vaep_total", 0)), 4),
                "offensive_value": round(float(row.get("vaep_offensive", 0)), 4),
                "start_x": float(row.get("start_x", 0) or 0),
                "start_y": float(row.get("start_y", 0) or 0),
                "end_x": float(row.get("end_x", 0) or 0),
                "end_y": float(row.get("end_y", 0) or 0),
            }
        )

    total = sum(p.get("total_vaep", 0) for p in ratings)
    offensive = sum(p.get("offensive_vaep", 0) for p in ratings)
    defensive = sum(p.get("defensive_vaep", 0) for p in ratings)

    return {
        "team_id": team_id,
        "total_vaep": round(float(total), 3),
        "offensive_vaep": round(float(offensive), 3),
        "defensive_vaep": round(float(defensive), 3),
        "player_ranks": ratings[:10],
        "top_valuable_actions": top_actions,
        "methodology": "VAEP",
        "metrics": metrics,
    }

@lru_cache(maxsize=64)
def sum_box(team_id: int, n_games: int, n_top: int, mark: tuple) -> Dict:
    events = match_events(team_id, n_games, include_opponent=True, normalize_mode="none", spadl=False)
    if len(events) == 0:
        return {}
    return team_sum(events, team_id, n_top)

@lru_cache(maxsize=64)
def vals_box(team_id: int, n_games: int, n_top_actions: int, mark: tuple) -> Dict:
    events = match_events(team_id, n_games, include_opponent=True, normalize_mode="none", spadl=False)
    if len(events) == 0:
        return {}
    return team_vals(events, team_id, n_top_actions)
