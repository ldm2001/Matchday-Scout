#!/usr/bin/env python3
# 데이터 갱신 후 VAEP 모델 디스크 캐시 재생성
# 사용법: cd backend && python scripts/prewarm_vaep.py
from __future__ import annotations

import sys
import time
from pathlib import Path

# backend 루트를 임포트 경로에 추가
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
    print(f"[prewarm] 학습 및 저장 완료 ({elapsed:.1f}s)")
    print(f"[prewarm] 메트릭: {models.metrics}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
