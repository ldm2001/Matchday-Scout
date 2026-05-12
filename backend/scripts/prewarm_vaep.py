#!/usr/bin/env python3
# VAEP 모델 디스크 캐시 사전 빌드 스크립트.
# 데이터(events/matches) 갱신 후 1회 실행해 backend/.cache/vaep/*.pkl 을 갱신한다.
# 산출물 .pkl 은 git tracking 되어 첫 사용자 cold-start 비용(~3분) 을 ~5초로 압축한다.
#
# 사용법: cd backend && python scripts/prewarm_vaep.py
from __future__ import annotations

import sys
import time
from pathlib import Path

# backend 루트를 import path 에 추가 (이 스크립트는 backend/scripts/ 하위)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.core.data import data_stamp, matches, raw  # noqa: E402
from services.vaep.model import vaep_models  # noqa: E402


def main() -> int:
    t0 = time.time()
    print("[prewarm] 데이터 로드 시작")
    raw()
    matches()
    stamp = data_stamp()
    print(f"[prewarm] 데이터 stamp: {stamp}")

    print("[prewarm] VAEP 듀얼 모델 학습 시작 (CatBoost 400 iter x 2)")
    models = vaep_models()
    elapsed = time.time() - t0
    print(f"[prewarm] 학습/저장 완료 ({elapsed:.1f}s)")
    print(f"[prewarm] 메트릭: {models.metrics}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
