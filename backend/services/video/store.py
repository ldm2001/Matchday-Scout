from dataclasses import dataclass
from threading import Lock
from time import time
from typing import Dict, Optional


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


class Store:
    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: Dict[str, Job] = {}

    def add(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.id] = job

    def one(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def set(self, job_id: str, **vals) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            for key, val in vals.items():
                setattr(job, key, val)
            job.updated = time()
            return job
