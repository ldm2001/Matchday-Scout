# Phase splitting and tactic pattern mining (Decroos et al. aligned)
from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

from .spadl import action_rows, spadl_map


class PhaseAnalyzer:
    PHASE_GAP_SECONDS = 10
    MIN_PHASE_EVENTS = 3

    def __init__(self, events_df: pd.DataFrame):
        self.events = events_df.sort_values(["game_id", "period_id", "time_seconds", "action_id"])

    def phase_list(self) -> List[pd.DataFrame]:
        phases: List[pd.DataFrame] = []

        for game_id in self.events["game_id"].unique():
            game_events = self.events[self.events["game_id"] == game_id].reset_index(drop=True)
            if game_events.empty:
                continue

            current_phase: List[pd.Series] = []
            prev_time = None
            prev_team = None
            prev_period = None

            for _, row in game_events.iterrows():
                curr_time = row.get("time_seconds", 0)
                curr_team = row.get("team_id", None)
                curr_period = row.get("period_id", None)
                new_phase = False

                if prev_time is not None:
                    if curr_time - prev_time > self.PHASE_GAP_SECONDS:
                        new_phase = True
                    elif prev_team is not None and curr_team is not None and curr_team != prev_team:
                        new_phase = True
                    elif prev_period is not None and curr_period is not None and curr_period != prev_period:
                        new_phase = True

                if new_phase and len(current_phase) >= self.MIN_PHASE_EVENTS:
                    phases.append(pd.DataFrame(current_phase))
                    current_phase = []

                current_phase.append(row)
                prev_time = curr_time
                prev_team = curr_team
                prev_period = curr_period

            if len(current_phase) >= self.MIN_PHASE_EVENTS:
                phases.append(pd.DataFrame(current_phase))

        return phases

    def phase_stats(self, phase: pd.DataFrame) -> Dict:
        if phase.empty:
            return {}

        features = {
            "length": len(phase),
            "duration": float(phase["time_seconds"].max() - phase["time_seconds"].min()),
            "start_x": float(phase.iloc[0].get("start_x", 0) or 0),
            "start_y": float(phase.iloc[0].get("start_y", 0) or 0),
            "end_x": float(phase.iloc[-1].get("end_x", 0) or 0),
            "end_y": float(phase.iloc[-1].get("end_y", 0) or 0),
            "avg_x": float(phase["start_x"].mean()) if "start_x" in phase.columns else 0.0,
            "avg_y": float(phase["start_y"].mean()) if "start_y" in phase.columns else 0.0,
            "pass_count": int((phase["type_name"] == "Pass").sum()) if "type_name" in phase.columns else 0,
            "carry_count": int((phase["type_name"] == "Carry").sum()) if "type_name" in phase.columns else 0,
            "shot_count": int((phase["type_name"] == "Shot").sum()) if "type_name" in phase.columns else 0,
            "cross_count": int((phase["type_name"] == "Cross").sum()) if "type_name" in phase.columns else 0,
            "forward_progress": float(phase["dx"].sum()) if "dx" in phase.columns else 0.0,
            "lateral_movement": float(abs(phase["dy"]).sum()) if "dy" in phase.columns else 0.0,
            "event_sequence": "_".join(phase["type_name"].tolist()) if "type_name" in phase.columns else "",
        }

        if "result_name" in phase.columns:
            results = phase["result_name"].value_counts()
            total = len(phase[phase["result_name"].notna()])
            features["success_rate"] = results.get("Successful", 0) / total if total > 0 else 0

        return features

    def zone_tag(self, x: float, y: float) -> str:
        x_zone = "수비" if x < 35 else ("중앙" if x < 70 else "공격")
        y_zone = "좌측" if y < 22.67 else ("중앙" if y < 45.33 else "우측")
        if x >= 88.5:
            x_zone = "박스"
        return f"{x_zone}_{y_zone}"


class PatternMiner:
    def __init__(self, phases: List[pd.DataFrame]):
        self.phases = phases
        self.phase_stats: List[Dict] = []

    def _phase_stats(self, phase: pd.DataFrame) -> Dict:
        analyzer = PhaseAnalyzer(phase)
        return analyzer.phase_stats(phase)

    def feat_list(self):
        self.phase_stats = []
        for i, phase in enumerate(self.phases):
            features = self._phase_stats(phase)
            features["phase_id"] = i
            self.phase_stats.append(features)
        return self.phase_stats

    def dtw_dist(self, seq_a: np.ndarray, seq_b: np.ndarray) -> float:
        n, m = len(seq_a), len(seq_b)
        if n == 0 or m == 0:
            return float("inf")
        dp = np.full((n + 1, m + 1), np.inf)
        dp[0, 0] = 0.0
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                cost = np.linalg.norm(seq_a[i - 1] - seq_b[j - 1])
                dp[i, j] = cost + min(dp[i - 1, j], dp[i, j - 1], dp[i - 1, j - 1])
        return float(dp[n, m])

    def phase_seq(self, phase: pd.DataFrame) -> np.ndarray:
        xs = pd.to_numeric(phase.get("start_x", 0), errors="coerce").fillna(0).to_numpy()
        ys = pd.to_numeric(phase.get("start_y", 0), errors="coerce").fillna(0).to_numpy()
        return np.stack([xs, ys], axis=1)

    def dist_mat(self) -> np.ndarray:
        seqs = [self.phase_seq(p) for p in self.phases]
        n = len(seqs)
        dist = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                d = self.dtw_dist(seqs[i], seqs[j])
                dist[i, j] = d
                dist[j, i] = d
        return dist

    def cluster_set(self, n_clusters: int = 100) -> Dict:
        if not self.phase_stats:
            self.feat_list()

        if len(self.phases) <= 1:
            return {}

        n_clusters = min(n_clusters, len(self.phases))
        dist = self.dist_mat()
        condensed = squareform(dist)
        tree = linkage(condensed, method="complete")
        labels = fcluster(tree, t=n_clusters, criterion="maxclust")

        clusters: Dict[int, Dict] = {}
        for i, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = {
                    "phases": [],
                    "count": 0,
                    "shot_phases": 0,
                    "shot_total": 0,
                    "avg_features": {},
                }
            clusters[label]["phases"].append(i)
            clusters[label]["count"] += 1
            shot_count = int(self.phase_stats[i].get("shot_count", 0))
            clusters[label]["shot_total"] += shot_count
            if shot_count > 0:
                clusters[label]["shot_phases"] += 1

        feature_cols = [
            "length",
            "duration",
            "start_x",
            "start_y",
            "end_x",
            "end_y",
            "avg_x",
            "avg_y",
            "pass_count",
            "carry_count",
            "forward_progress",
            "lateral_movement",
        ]
        for label in clusters:
            phase_indices = clusters[label]["phases"]
            for col in feature_cols:
                clusters[label]["avg_features"][col] = float(
                    np.mean([self.phase_stats[i].get(col, 0) for i in phase_indices])
                )
            clusters[label]["shot_conversion_rate"] = clusters[label]["shot_phases"] / max(
                clusters[label]["count"], 1
            )

        return clusters

    def pattern_top(self, n_top: int = 3) -> List[Dict]:
        clusters = self.cluster_set()
        if not clusters:
            return []

        sorted_clusters = sorted(
            clusters.items(), key=lambda x: (x[1]["shot_total"], x[1]["shot_conversion_rate"]), reverse=True
        )

        patterns: List[Dict] = []
        for label, info in sorted_clusters[:n_top]:
            sequences = [self.phase_code(self.phases[i]) for i in info["phases"]]
            common = self.seq_freq(sequences)

            patterns.append(
                {
                    "cluster_id": int(label),
                    "frequency": info["count"],
                    "shot_total": int(info["shot_total"]),
                    "shot_conversion_rate": round(info["shot_conversion_rate"], 3),
                    "avg_duration": round(info["avg_features"].get("duration", 0), 1),
                    "avg_passes": round(info["avg_features"].get("pass_count", 0), 1),
                    "avg_forward_progress": round(info["avg_features"].get("forward_progress", 0), 1),
                    "avg_start_zone": self.zone_tag(
                        info["avg_features"].get("start_x", 0),
                        info["avg_features"].get("start_y", 0),
                    ),
                    "avg_end_zone": self.zone_tag(
                        info["avg_features"].get("end_x", 0),
                        info["avg_features"].get("end_y", 0),
                    ),
                    "common_sequences": common[:3],
                }
            )

        return patterns

    def zone_tag(self, x: float, y: float) -> str:
        x_zone = "수비" if x < 35 else ("중앙" if x < 70 else "공격")
        y_zone = "좌측" if y < 22.67 else ("중앙" if y < 45.33 else "우측")
        if x >= 88.5:
            x_zone = "박스"
        return f"{x_zone}_{y_zone}"

    def phase_code(self, phase: pd.DataFrame) -> List[str]:
        phase = spadl_map(phase)
        phase = action_rows(phase)
        encoded: List[str] = []
        for _, event in phase.iterrows():
            action = str(event.get("spadl_type", event.get("type_name", "action")))
            sx = float(event.get("start_x", 0) or 0)
            sy = float(event.get("start_y", 0) or 0)
            ex = float(event.get("end_x", sx) or sx)
            ey = float(event.get("end_y", sy) or sy)
            start_zone = self.zone_tag(sx, sy)
            end_zone = self.zone_tag(ex, ey)

            if action in {"pass", "cross", "corner_crossed", "freekick_crossed", "throw_in", "goal_kick", "dribble"}:
                token = f"{action} FROM {start_zone} TO {end_zone}"
            else:
                token = f"{action} AT {start_zone}"
            encoded.append(token)
        return encoded

    def seq_freq(self, sequences: List[List[str]]) -> List[str]:
        if not sequences:
            return []

        min_support = max(2, int(len(sequences) * 0.1))
        max_len = 4
        support_counter: Counter = Counter()

        for seq in sequences:
            seq_len = len(seq)
            seen = set()
            for length in range(2, min(max_len, seq_len) + 1):
                for idxs in _seq_idx(seq_len, length):
                    pattern = tuple(seq[i] for i in idxs)
                    seen.add(pattern)
            for pattern in seen:
                support_counter[pattern] += 1

        scored = []
        for pattern, support in support_counter.items():
            if support < min_support:
                continue
            score = support * seq_weight(pattern)
            scored.append((score, support, pattern))

        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [" -> ".join(pat) for _, _, pat in scored[:10]]


def _seq_idx(n: int, length: int) -> Iterable[Tuple[int, ...]]:
    if length <= 0 or n < length:
        return []
    indices = list(range(n))
    if length == 1:
        return [(i,) for i in indices]
    result = []

    def rec(start: int, path: List[int]):
        if len(path) == length:
            result.append(tuple(path))
            return
        for i in range(start, n):
            rec(i + 1, path + [i])

    rec(0, [])
    return result


def seq_weight(pattern: Tuple[str, ...]) -> float:
    weights = {
        "shot": 2.0,
        "pass": 0.5,
    }
    score = 0.0
    for token in pattern:
        action = token.split()[0]
        score += weights.get(action, 1.0)
    return score


def team_pat(events_df: pd.DataFrame, team_id: int, n_patterns: int = 3) -> List[Dict]:
    analyzer = PhaseAnalyzer(events_df)
    phases = analyzer.phase_list()
    if not phases:
        return []

    # Keep phases that start with the team of interest.
    team_phases = [p for p in phases if int(p.iloc[0].get("team_id", -1)) == int(team_id)]
    if not team_phases:
        return []

    miner = PatternMiner(team_phases)
    return miner.pattern_top(n_patterns)
