from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from time import time
from typing import Any

# 캐시 루트 경로
ROOT = Path(__file__).resolve().parents[2]
# 비디오 캐시 경로
CACHE = ROOT / "cache" / "video"
# 작업 DB 경로
DB = CACHE / "jobs.sqlite3"
# 공통 조회 컬럼
COLS = "id, url, status, created, updated, file_path, report, error"
# 중단 복구 메시지
HALT = "worker interrupted"

# 작업 레코드 모델
@dataclass
class Job:
    # 작업 ID
    id: str
    # 입력 URL
    url: str
    # 현재 상태
    status: str
    # 생성 시각
    created: float
    # 수정 시각
    updated: float
    # 업로드 파일 경로
    file_path: str | None = None
    # 분석 결과
    report: dict[str, Any] | None = None
    # 실패 메시지
    error: str | None = None

# 작업 저장소
class Store:
    # 수정 허용 필드
    FIELDS = {"url", "status", "file_path", "report", "error"}

    # 저장소 초기화
    def __init__(self, db: Path | None = None, heal: bool = True) -> None:
        # 스레드 락 준비
        self._lock = Lock()
        # DB 경로 결정
        self._db = db or DB
        # 상위 폴더 보장
        self._db.parent.mkdir(parents=True, exist_ok=True)
        # 테이블 생성
        self._init()
        # 중단 작업 복구
        if heal:
            self.heal()

    # DB 연결 생성
    def _conn(self) -> sqlite3.Connection:
        # 연결 열기
        conn = sqlite3.connect(self._db, timeout=30)
        # 행 객체 설정
        conn.row_factory = sqlite3.Row
        # WAL 모드 설정
        conn.execute("PRAGMA journal_mode=WAL")
        # 동기화 강도 설정
        conn.execute("PRAGMA synchronous=FULL")
        # 연결 반환
        return conn

    # 테이블 생성
    def _init(self) -> None:
        # 락과 연결 확보
        with self._lock, self._conn() as conn:
            # jobs 테이블 보장
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created REAL NOT NULL,
                    updated REAL NOT NULL,
                    file_path TEXT,
                    report TEXT,
                    error TEXT
                )
                """
            )

    # 중단 작업 복구
    def heal(self) -> None:
        # 복구 시각 기록
        now = time()
        # 락과 연결 확보
        with self._lock, self._conn() as conn:
            # 실행 중 작업 실패 처리
            conn.execute(
                """
                UPDATE jobs
                SET status = 'fail',
                    report = NULL,
                    error = COALESCE(NULLIF(error, ''), ?),
                    updated = ?
                WHERE status IN ('queued', 'run')
                """,
                (HALT, now),
            )

    # 결과 JSON 직렬화
    def _blob(self, data: dict[str, Any] | None) -> str | None:
        # 빈 값은 그대로 둠
        if data is None:
            return None
        # JSON 문자열로 변환
        return json.dumps(data, ensure_ascii=False)

    # 결과 JSON 역직렬화
    def _data(self, text: str | None) -> dict[str, Any] | None:
        # 빈 값은 None 처리
        if not text:
            return None
        # JSON 딕셔너리 복원
        return json.loads(text)

    # 행을 모델로 변환
    def _job(self, row: sqlite3.Row | None) -> Job | None:
        # 없으면 None 반환
        if row is None:
            return None
        # Job 객체 생성
        return Job(
            id=row["id"],
            url=row["url"],
            status=row["status"],
            created=float(row["created"]),
            updated=float(row["updated"]),
            file_path=row["file_path"],
            report=self._data(row["report"]),
            error=row["error"],
        )

    # 연결 안에서 단건 조회
    def _item(self, conn: sqlite3.Connection, job_id: str) -> Job | None:
        # 단건 레코드 조회
        row = conn.execute(
            f"SELECT {COLS} FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        # 모델로 변환
        return self._job(row)

    # 신규 작업 저장
    def slot(self, job: Job) -> None:
        # 락과 연결 확보
        with self._lock, self._conn() as conn:
            # 신규 레코드 삽입
            conn.execute(
                """
                INSERT INTO jobs (id, url, status, created, updated, file_path, report, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.url,
                    job.status,
                    job.created,
                    job.updated,
                    job.file_path,
                    self._blob(job.report),
                    job.error,
                ),
            )

    # 작업 단건 조회
    def item(self, job_id: str) -> Job | None:
        # 락과 연결 확보
        with self._lock, self._conn() as conn:
            # 내부 조회 호출
            return self._item(conn, job_id)

    # 작업 부분 수정
    def patch(self, job_id: str, **vals: Any) -> Job | None:
        # 빈 수정은 조회로 처리
        if not vals:
            return self.item(job_id)

        # 수정 컬럼 목록
        cols: list[str] = []
        # SQL 인자 목록
        args: list[Any] = []
        # 전달 필드 순회
        for key, val in vals.items():
            # 허용되지 않은 필드 차단
            if key not in self.FIELDS:
                raise KeyError(f"unsupported job field: {key}")
            # SET 절 추가
            cols.append(f"{key} = ?")
            # 값 인자 추가
            args.append(self._blob(val) if key == "report" else val)

        # 수정 시각 컬럼 추가
        cols.append("updated = ?")
        # 수정 시각 값 추가
        args.append(time())
        # 마지막 조건 인자 추가
        args.append(job_id)

        # 락과 연결 확보
        with self._lock, self._conn() as conn:
            # 업데이트 실행
            cur = conn.execute(
                f"UPDATE jobs SET {', '.join(cols)} WHERE id = ?",
                args,
            )
            # 대상이 없으면 종료
            if cur.rowcount == 0:
                return None
            # 최신 레코드 반환
            return self._item(conn, job_id)
