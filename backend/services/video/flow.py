from concurrent.futures import ThreadPoolExecutor
from time import time
from typing import Optional
from uuid import uuid4

from .pipe import Pipe, payload
from .store import Job, Store

_store = Store()
_pipe = Pipe()
_pool = ThreadPoolExecutor(max_workers=1)


def _ts() -> float:
    return time()


def _task(job_id: str) -> None:
    job = _store.item(job_id)
    if not job:
        return
    _store.patch(job_id, status="run")
    try:
        report = _pipe.flow(job.id, job.url, job.file_path)
        _store.patch(job_id, status=report.status, report=payload(report))
    except Exception as err:
        _store.patch(job_id, status="fail", error=str(err))


def job_slot(url: str, file_path: str | None = None) -> Job:
    job_id = uuid4().hex
    job = Job(
        id=job_id,
        url=url,
        status="queued",
        created=_ts(),
        updated=_ts(),
        file_path=file_path,
    )
    _store.slot(job)
    _pool.submit(_task, job_id)
    return job


def job_item(job_id: str) -> Optional[Job]:
    return _store.item(job_id)
