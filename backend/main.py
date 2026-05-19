# uvicorn main:app --reload --port 8000
import os
import threading
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import teams, patterns, setpieces, network, simulation, video
from services.core.data import data_stamp
from services.warmup import warm_all

# FastAPI 앱 초기화
app = FastAPI(
    title="Matchday Scout API",
    description="K리그 이벤트 데이터 기반 AI 전술 분석 API",
    version="1.0.0"
)

# 프런트엔드 허용 도메인
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3001").split(",")

# CORS 미들웨어
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)

# 헬스 라우터 - /api 프리픽스 아래로 통합
health_router = APIRouter()

_CACHE_ROOT = Path(__file__).resolve().parent / ".cache"


@health_router.get("/health")
def health():
    return {"status": "healthy"}


# 캐시 상태 진단 - data_stamp + 디스크 캐시 파일 목록 반환
@health_router.get("/health/cache")
def health_cache():
    raw_mark, match_mark = data_stamp()
    files: dict[str, list[dict]] = {}
    if _CACHE_ROOT.exists():
        for sub in sorted(p for p in _CACHE_ROOT.iterdir() if p.is_dir()):
            entries = []
            for f in sorted(sub.glob("*")):
                if not f.is_file():
                    continue
                try:
                    entries.append({"name": f.name, "size": f.stat().st_size})
                except OSError:
                    continue
            files[sub.name] = entries
    return {
        "data_stamp": {
            "raw": {"size": raw_mark[0], "sha256_prefix": raw_mark[1]},
            "matches": {"size": match_mark[0], "sha256_prefix": match_mark[1]},
        },
        "disk_cache": files,
    }


# 도메인별 라우터
app.include_router(health_router, prefix="/api", tags=["Health"])
# 팀 통계
app.include_router(teams.router, prefix="/api/teams", tags=["Teams"])
# 공격 패턴
app.include_router(patterns.router, prefix="/api/patterns", tags=["Patterns"])
# 세트피스
app.include_router(setpieces.router, prefix="/api/setpieces", tags=["Set-pieces"])
# 패스 네트워크
app.include_router(network.router, prefix="/api/network", tags=["Network"])
# 승률 예측 VAEP 시뮬레이션
app.include_router(simulation.router, prefix="/api/simulation", tags=["Simulation"])
# 영상 분석
app.include_router(video.router, prefix="/api/video", tags=["Video"])


# 루트
@app.get("/")
def root():
    return {"message": "Matchday Scout API", "status": "running"}


# 서버 시작 시 백그라운드 스레드로 사전 워밍 (services.warmup.warm_all로 위임)
@app.on_event("startup")
def ready_box():
    threading.Thread(target=warm_all, name="analysis-prewarm", daemon=True).start()
