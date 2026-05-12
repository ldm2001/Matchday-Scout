# uvicorn main:app --reload --port 8000
import os
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import teams, patterns, setpieces, network, simulation, video
from services.core.data import raw, matches
from services.vaep.model import vaep_models

# FastAPI 앱 초기화
app = FastAPI(
    title="Matchday Scout API",
    description="K리그 이벤트 데이터 기반 AI 전술 분석 API",
    version="1.0.0"
)

# 프런트엔드 허용 도메인
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

# CORS 미들웨어
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)

# 도메인별 라우터
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


# 루트 헬스체크
@app.get("/")
def root():
    return {"message": "Matchday Scout API", "status": "running"}

# 헬스체크
@app.get("/health")
def health():
    return {"status": "healthy"}


# 서버 시작 시 백그라운드 스레드로 모델 사전 로드
@app.on_event("startup")
def ready_box():
    def _warm():
        try:
            # 이벤트 원본 로드
            raw()
            # 경기 데이터 로드
            matches()
            # VAEP 모델 사전 학습
            vaep_models()
        except Exception:
            # 웜업 실패해도 서버는 계속 가동
            pass

    threading.Thread(target=_warm, name="vaep-prewarm", daemon=True).start()
