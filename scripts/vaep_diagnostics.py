#!/usr/bin/env python3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.data_loader import raw, matches
from backend.services.vaep_model import vaep_models


def data_quality_report(events: pd.DataFrame) -> None:
    print("Data quality checks")
    print("- total events:", len(events))
    for col in ["start_x", "start_y", "end_x", "end_y", "time_seconds", "team_id"]:
        if col in events.columns:
            missing = events[col].isna().sum()
            print(f"- missing {col}: {missing}")

    dup = events.duplicated(subset=["game_id", "action_id"]).sum()
    print("- duplicate (game_id, action_id):", dup)

    # Time order issues: count games with non-monotonic timestamps
    non_mono = 0
    for game_id in events["game_id"].unique():
        game = events[events["game_id"] == game_id].sort_values(["period_id", "action_id"])
        times = pd.to_numeric(game["time_seconds"], errors="coerce").fillna(0)
        if not times.is_monotonic_increasing:
            non_mono += 1
    print("- games with non-monotonic time_seconds:", non_mono)


def main() -> None:
    events = raw()
    _ = matches()
    data_quality_report(events)

    models = vaep_models()
    print("\nVAEP validation metrics")
    for k, v in models.metrics.items():
        print(f"- {k}: {v:.4f}" if isinstance(v, float) else f"- {k}: {v}")

    if models.metrics.get("score_accuracy", 0) < 0.9 or models.metrics.get("concede_accuracy", 0) < 0.9:
        print("\nWARNING: Accuracy below 0.90. Consider more data/features or tuning.")


if __name__ == "__main__":
    main()
