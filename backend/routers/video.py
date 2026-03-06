from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from services.video import job_slot as job_slot_core, job_item as job_item_core

# 비디오 관련 API 엔드포인트를 묶어줄 라우터 객체 생성
router = APIRouter()

# 직접 업로드된 비디오 파일을 임시 보관할 캐시 디렉터리 경로 설정
CACHE = Path(__file__).resolve().parents[1] / "cache" / "video"
# 캐시 디렉터리가 없으면 생성 (부모 경로 포함, 이미 있어도 무시)
CACHE.mkdir(parents=True, exist_ok=True)

# 비디오 분석 요청 페이로드 스키마 정의 클래스
class VideoReq(BaseModel):
    # 분석 대상 URL 주소
    url: str

# 데이터베이스 응답 모델을 클라이언트 친화적 딕셔너리로 변환하는 헬퍼 함수
def job_card(job) -> dict:
    return {
        "job_id": job.id, # 분석 작업의 고유 ID
        "status": job.status, # 분석 작업의 현재 상태
        "created": job.created,  # 작업이 최초 생성된 시점 문자열
        "updated": job.updated, # 작업 상태가 마지막으로 업데이트된 시점 문자열
        "report": job.report, # 분석 완료 시 생성되는 결과 리포트 JSON
        "error": job.error, # 분석 처리 중 발생한 예외/에러 메시지
    }

# URL을 입력받아 신규 분석 작업을 예약하는 API 라우트
@router.post("/jobs")
def job_slot(req: VideoReq):
    # 요청 바디에 URL 문자열이 비어있으면 400 에러 처리
    if not req.url:
        raise HTTPException(status_code=400, detail="url required")
    # 비즈니스 로직에 URL을 넘겨 신규 작업을 스케줄링하고 Job 엔티티 반환
    job = job_slot_core(req.url)
    # 예약된 상태의 Job 엔티티를 정제하여 리턴
    return job_card(job)

# 비디오 파일을 직접 서버로 업로드하여 분석 작업을 예약하는 API 라우트
@router.post("/upload")
def job_file(file: UploadFile = File(...), url: str = Form("")):
    # 폼 영역에 파일이 정상적으로 포함되었는지 검증
    if not file.filename:
        raise HTTPException(status_code=400, detail="file required")
    # 파일명에서 확장자만 추출하여 소문자로 변환
    ext = Path(file.filename).suffix.lower()
    # 허용되지 않는 비디오 포맷인 경우 400 에러 처리
    if ext not in {".mp4", ".mov", ".mkv"}:
        raise HTTPException(status_code=400, detail="unsupported file")
    # 업로드되는 파일의 충돌 방지를 위한 랜덤 UUID 파일명 발급
    name = f"{uuid4().hex}{ext}"
    # 최종 저장될 캐시 디렉터리 타겟 경로 객체 조합
    path = CACHE / name
    # 메모리 버퍼를 열고 실제 물리 디스크에 파일 청크 단위 저장
    with path.open("wb") as handle:
        while True:
            # 한 번에 1MB 크기씩 나눠서 메모리에 적재
            chunk = file.file.read(1024 * 1024)
            # 더 이상 읽을 파일 조각이 없으면 루프 탈출
            if not chunk:
                break
            # 읽어들인 1MB 청크를 실제 디스크 파일에 기록
            handle.write(chunk)
    # 폼으로 전송된 URL 혹은 임시 로컬 파일 경로를 기반으로 작업 스케줄링
    job = job_slot_core(url or str(path), str(path))
    # 예약 완료된 Job 엔티티를 정제하여 리턴
    return job_card(job)

# 고유 Job ID를 통해 비디오 분석 진행도 및 결과를 조회하는 API 라우트
@router.get("/jobs/{job_id}")
def job_info(job_id: str):
    # 비즈니스 로직에 ID를 넘겨 최신 Job 상태 데이터베이스 패치
    job = job_item_core(job_id)
    # 전달받은 ID를 가진 작업 내역이 없으면 404 에러 처리
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    # 검색된 Job 엔티티를 프론트엔드 포맷에 맞게 정제하여 송출
    return job_card(job)
