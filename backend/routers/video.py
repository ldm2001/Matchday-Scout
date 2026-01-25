from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from services.video import kick, grab

router = APIRouter()

CACHE = Path(__file__).resolve().parents[1] / "cache" / "video"
CACHE.mkdir(parents=True, exist_ok=True)

class VideoReq(BaseModel):
    url: str

def job_view(job) -> dict:
    return {
        "job_id": job.id,
        "status": job.status,
        "created": job.created,
        "updated": job.updated,
        "report": job.report,
        "error": job.error,
    }

@router.post("/jobs")
def job_new(req: VideoReq):
    if not req.url:
        raise HTTPException(status_code=400, detail="url required")
    job = kick(req.url)
    return job_view(job)

@router.post("/upload")
def job_upload(file: UploadFile = File(...), url: str = Form("")):
    if not file.filename:
        raise HTTPException(status_code=400, detail="file required")
    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp4", ".mov", ".mkv"}:
        raise HTTPException(status_code=400, detail="unsupported file")
    name = f"{uuid4().hex}{ext}"
    path = CACHE / name
    with path.open("wb") as handle:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    job = kick(url or str(path), str(path))
    return job_view(job)

@router.get("/jobs/{job_id}")
def job_item(job_id: str):
    job = grab(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job_view(job)
