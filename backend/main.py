# uvicorn main:app --reload --port 8000
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import teams, patterns, setpieces, network, simulation, video
from services.core.data import raw, matches
from services.vaep.model import vaep_models

# FastAPI 메인 애플리케이션 인스턴스 생성
# 프론트 노출용 메타데이터 설정
app = FastAPI(
    title="Matchday Scout API",
    description="K리그 이벤트 데이터 기반 AI 전술 분석 API",
    version="1.0.0"
)

# CORS 허용 출처 설정
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

# 애플리케이션에 CORS 미들웨어 등록 체인
app.add_middleware(
    CORSMiddleware,
    # 컴파일된 허용 도메인 문자열 배열 주입
    allow_origins=[origin.strip() for origin in CORS_ORIGINS],
    # 쿠키, 인증 헤더 등 자격 증명 정보 요청 허용
    allow_credentials=True,
    # 프론트에서 호출 가능한 HTTP 메서드 전면 허용
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    # 브라우저 커스텀 헤더 전면 허용 설정
    allow_headers=["Content-Type", "Authorization", "Accept"],
)

# 도메인 단위로 분할된 하위 라우터들을 메인 앱 트리에 부착 (URL Prefix 및 묶음 태그 지정)
# 팀 스탯 및 순위 조회 라우터
app.include_router(teams.router, prefix="/api/teams", tags=["Teams"])
# 공격 전술 패턴 및 국면 분석 라우터
app.include_router(patterns.router, prefix="/api/patterns", tags=["Patterns"])
# 코너킥 프리킥 등 세트피스 로직 분석 라우터
app.include_router(setpieces.router, prefix="/api/setpieces", tags=["Set-pieces"])
# 선수 간 패스망 허브 중앙성 지표 분석 라우터
app.include_router(network.router, prefix="/api/network", tags=["Network"])
# 경기 승률 예측 및 개인별 VAEP 압박 전술 시뮬레이션 라우터
app.include_router(simulation.router, prefix="/api/simulation", tags=["Simulation"])
# 사용자 업로드 비디오 전술 분석 파이프라인 라우터
app.include_router(video.router, prefix="/api/video", tags=["Video"])


# 서버 접속 상태를 리턴하는 베이직 루트 엔드포인트
@app.get("/")
def root():
    return {"message": "Matchday Scout API", "status": "running"}

# 클라우드 로드밸런서 타겟 그룹 등에서 서버 헬스체크용으로 호출할 API
@app.get("/health")
def health():
    return {"status": "healthy"}


# 서버가 켜질 때 단 1번 실행됨
@app.on_event("startup")
def ready_box():
    try:
        # 이벤트 원장 데이터 로드 수행
        raw()
        # 경기 매치 히스토리 데이터 로드 수행
        matches()
        # VAEP 베이스 통계 모델 등 무거운 자산 백그라운드 선탑재 수행
        vaep_models()
    except Exception:
        # 배포 직후 데이터 부재 등의 사유로 웜업이 실패해도 서버 구동 자체를 막지는 않음
        pass
