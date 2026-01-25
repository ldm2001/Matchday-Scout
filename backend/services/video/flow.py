from concurrent.futures import ThreadPoolExecutor
from time import time
from typing import Optional
from uuid import uuid4

from .pipe import Pipe, pack
from .store import Job, Store

_store = Store()
_pipe = Pipe()
_pool = ThreadPoolExecutor(max_workers=1)


def _now() -> float:
    return time()


def _work(job_id: str) -> None:
    job = _store.one(job_id)
    if not job:
        return
    _store.set(job_id, status="run")
    try:
        report = _pipe.run(job.id, job.url, job.file_path)
        _store.set(job_id, status=report.status, report=pack(report))
    except Exception as err:
        _store.set(job_id, status="fail", error=str(err))


def kick(url: str, file_path: str | None = None) -> Job:
    job_id = uuid4().hex
    job = Job(
        id=job_id,
        url=url,
        status="queued",
        created=_now(),
        updated=_now(),
        file_path=file_path,
    )
    _store.add(job)
    _pool.submit(_work, job_id)
    return job


def grab(job_id: str) -> Optional[Job]:
    return _store.one(job_id)
