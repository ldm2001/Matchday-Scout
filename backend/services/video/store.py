# 비디오 분석 작업 저장소 (인메모리)
from dataclasses import dataclass
from threading import Lock
from time import time
from typing import Dict, Optional


# 분석 작업 데이터
@dataclass
class Job:
    id: str
    url: str
    status: str
    created: float
    updated: float
    file_path: Optional[str] = None
    report: Optional[dict] = None
    error: Optional[str] = None


# 스레드 안전한 작업 저장소
class Store:
    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: Dict[str, Job] = {}

    # 새 작업 저장
    def slot(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.id] = job

    # 작업 ID로 조회
    def item(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    # 작업 상태 업데이트
    def patch(self, job_id: str, **vals) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            for key, val in vals.items():
                setattr(job, key, val)
            job.updated = time()
            return job
