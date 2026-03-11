from concurrent.futures import ThreadPoolExecutor
from time import time
from uuid import uuid4
from .pipe import Pipe, payload
from .store import Job, Store

# 작업 저장소 준비
_store = Store()
# 분석 파이프 준비
_pipe = Pipe()
# 단일 워커 준비
_pool = ThreadPoolExecutor(max_workers=1)

# 현재 시각 반환
def stamp() -> float:
    return time()

# 작업 본문 실행
def task(job_id: str) -> None:
    # 작업 조회
    job = _store.item(job_id)
    # 없는 작업은 종료
    if job is None:
        return

    # 실행 상태 저장
    _store.patch(job_id, status="run", error=None)
    try:
        # 분석 파이프 호출
        report = _pipe.flow(job.id, job.url, job.file_path)
        # 성공 결과 저장
        _store.patch(job_id, status=report.status, report=payload(report), error=None)
    except Exception as err:
        # 실패 결과 저장
        _store.patch(job_id, status="fail", report=None, error=str(err))

# 작업 등록 함수
def job_slot(url: str, file_path: str | None = None) -> Job:
    # 생성 시각 고정
    now = stamp()
    # 작업 객체 생성
    job = Job(
        id=uuid4().hex,
        url=url,
        status="queued",
        created=now,
        updated=now,
        file_path=file_path,
    )
    # 작업 원본 저장
    _store.slot(job)

    try:
        # 워커에 작업 제출
        _pool.submit(task, job.id)
    except Exception as err:
        # 제출 실패 반영
        failed = _store.patch(job.id, status="fail", report=None, error=str(err))
        # 실패 상태 반환
        return failed or job

    # 최신 상태 반환
    return _store.item(job.id) or job


# 작업 조회 함수
def job_item(job_id: str) -> Job | None:
    return _store.item(job_id)
