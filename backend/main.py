# uvicorn main:app --reload --port 8000
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import teams, patterns, setpieces, network, simulation, video
from services.core.data import raw, matches
from services.vaep.model import vaep_models

app = FastAPI(
    title="Matchday Scout API",
    description="K리그 이벤트 데이터 기반 AI 전술 분석 API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(teams.router, prefix="/api/teams", tags=["Teams"])
app.include_router(patterns.router, prefix="/api/patterns", tags=["Patterns"])
app.include_router(setpieces.router, prefix="/api/setpieces", tags=["Set-pieces"])
app.include_router(network.router, prefix="/api/network", tags=["Network"])
app.include_router(simulation.router, prefix="/api/simulation", tags=["Simulation"])
app.include_router(video.router, prefix="/api/video", tags=["Video"])


@app.get("/")
def root():
    return {"message": "Matchday Scout API", "status": "running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


# Cache warm for faster first responses
@app.on_event("startup")
def ready_box():
    try:
        raw()
        matches()
        vaep_models()
    except Exception:
        pass
