from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from services.video import job_item as job_item_core, job_slot as job_slot_core

CACHE = Path(__file__).resolve().parents[1] / ".cache" / "video" # 업로드 캐시 경로
EXTS = {".mp4", ".mov", ".mkv"} # 허용 확장자
CHUNK = 1024 * 1024 # 청크 크기

router = APIRouter() # 비디오 라우터
CACHE.mkdir(parents=True, exist_ok=True) # 캐시 폴더 보장

# 요청 바디 모델
class VideoReq(BaseModel):
    url: str # 입력 URL

# 응답 카드 변환
def card(job) -> dict:
    return {
        "job_id": job.id,
        "status": job.status,
        "created": job.created,
        "updated": job.updated,
        "report": job.report,
        "error": job.error,
    }

# 파일 확장자 추출
def ext(name: str) -> str:
    return Path(name).suffix.lower()

# 임시 파일 경로 생성
def part(path: Path) -> Path:
    return path.with_suffix(f"{path.suffix}.part")

# 업로드 파일 저장
def stash(file: UploadFile, path: Path) -> None:
    # 임시 파일 경로 계산
    tmp = part(path)
    try:
        # 임시 파일 쓰기
        with tmp.open("wb") as out:
            # 청크 단위로 복사
            while True:
                # 다음 청크 읽기
                chunk = file.file.read(CHUNK)
                # 끝이면 종료
                if not chunk:
                    break
                # 청크 기록
                out.write(chunk)
        # 최종 파일로 교체
        tmp.replace(path)
    except Exception:
        # 임시 파일 정리
        if tmp.exists():
            tmp.unlink()
        # 예외 재전파
        raise

# URL 작업 생성
@router.post("/jobs")
def job_slot(req: VideoReq):
    # 빈 URL 차단
    if not req.url:
        raise HTTPException(status_code=400, detail="url required")
    # 작업 카드 반환
    return card(job_slot_core(req.url))

# 파일 업로드 작업 생성
@router.post("/upload")
def job_file(file: UploadFile = File(...), url: str = Form("")):
    # 파일명 존재 확인
    if not file.filename:
        raise HTTPException(status_code=400, detail="file required")

    # 확장자 계산
    suffix = ext(file.filename)
    # 확장자 검증
    if suffix not in EXTS:
        raise HTTPException(status_code=400, detail="unsupported file")

    # 최종 저장 경로 생성
    path = CACHE / f"{uuid4().hex}{suffix}"
    try:
        # 업로드 파일 저장
        stash(file, path)
        # 분석 작업 등록
        job = job_slot_core(url or str(path), str(path))
    except Exception:
        # 실패 파일 정리
        if path.exists():
            path.unlink()
        # 예외 재전파
        raise
    finally:
        # 업로드 핸들 정리
        file.file.close()

    # 작업 카드 반환
    return card(job)

# 작업 조회 API
@router.get("/jobs/{job_id}")
def job_info(job_id: str):
    # 작업 조회
    job = job_item_core(job_id)
    # 없으면 404 반환
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    # 작업 카드 반환
    return card(job)
