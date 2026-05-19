# 단일 비행(single-flight) 캐시 + 2단(L1 메모리 + L2 디스크) 캐시
# 무거운 분석 함수가 여러 스레드에서 동시에 호출될 때 1회만 계산하도록 보장하고,
# 프로세스 재시작 후에도 L2(DiskCache)로 콜드 스타트 지연을 제거
import hashlib
import threading
from collections import OrderedDict
from functools import wraps
from pathlib import Path
from typing import Literal, Optional

from .cache_store import DiskCache

# layered_cache 기본 base_dir = <project_root>/.cache/<name>/
# cache.py(backend/services/core/) → parents[3] = 프로젝트 루트
_DEFAULT_CACHE_ROOT = Path(__file__).resolve().parents[3] / ".cache"


def single_flight(maxsize: int = 128):
    def decorator(fn):
        cache: "OrderedDict[tuple, object]" = OrderedDict()
        master = threading.Lock()
        key_locks: "dict[tuple, threading.Lock]" = {}

        @wraps(fn)
        def wrapper(*args):
            # 빠른 경로: 캐시 적중 시 즉시 반환
            with master:
                if args in cache:
                    cache.move_to_end(args)
                    return cache[args]
                key_lock = key_locks.setdefault(args, threading.Lock())

            # 키 단위 잠금: 같은 키 동시 호출자는 직렬화, 다른 키는 독립적으로 진행
            with key_lock:
                with master:
                    if args in cache:
                        cache.move_to_end(args)
                        return cache[args]

                result = fn(*args)

                with master:
                    cache[args] = result
                    cache.move_to_end(args)
                    while len(cache) > maxsize:
                        cache.popitem(last=False)
                    key_locks.pop(args, None)

                return result

        wrapper.cache_clear = lambda: (cache.clear(), key_locks.clear())  # type: ignore[attr-defined]
        return wrapper

    return decorator


def _stable_key(args: tuple) -> str:
    """args 튜플을 파일명-safe 안정 문자열로 변환.
    convention: 마지막 인자는 mark 튜플(sha256 해시 처리), 나머지는 직렬 가능한 단순 값.
    예: (1, 5, 3, ((1024, "abc..."), (2048, "def..."))) → "1_5_3_<sha256[:12]>"."""
    if not args:
        return "empty"
    *simple, mark = args
    mark_hex = hashlib.sha256(repr(mark).encode("utf-8")).hexdigest()[:12]
    if simple:
        prefix = "_".join(str(s) for s in simple)
        return f"{prefix}_{mark_hex}"
    return mark_hex


def layered_cache(
    name: str,
    serde: Literal["pickle", "parquet"] = "pickle",
    maxsize: int = 256,
    base_dir: Optional[Path] = None,
):
    """L1(메모리 single-flight) + L2(DiskCache) 2단 캐시 데코레이터.

    조회 순서:
        1) L1 적중 → 반환
        2) L2 적중 → L1 promote 후 반환
        3) 둘 다 miss → fn 호출 → L2 put → L1 put

    같은 키 동시 호출은 per-key lock으로 직렬화되어 fn은 1회만 실행된다.
    L2 실패는 WARNING 로그로만 가시화하고 L1은 정상 채워진다."""
    disk_dir = base_dir if base_dir is not None else _DEFAULT_CACHE_ROOT / name
    disk = DiskCache(name=name, serde=serde, base_dir=disk_dir)

    def decorator(fn):
        l1: "OrderedDict[tuple, object]" = OrderedDict()
        master = threading.Lock()
        key_locks: "dict[tuple, threading.Lock]" = {}

        @wraps(fn)
        def wrapper(*args):
            # 1) L1 빠른 경로
            with master:
                if args in l1:
                    l1.move_to_end(args)
                    return l1[args]
                key_lock = key_locks.setdefault(args, threading.Lock())

            # 2) 키 단위 잠금
            with key_lock:
                with master:
                    if args in l1:
                        l1.move_to_end(args)
                        return l1[args]

                # 3) L2 적중 여부 확인
                l2_key = _stable_key(args)
                cached = disk.get(l2_key)
                if cached is not None:
                    with master:
                        l1[args] = cached
                        l1.move_to_end(args)
                        while len(l1) > maxsize:
                            l1.popitem(last=False)
                        key_locks.pop(args, None)
                    return cached

                # 4) 둘 다 miss → 실제 계산 → L2 put → L1 put
                result = fn(*args)
                disk.put(l2_key, result)
                with master:
                    l1[args] = result
                    l1.move_to_end(args)
                    while len(l1) > maxsize:
                        l1.popitem(last=False)
                    key_locks.pop(args, None)
                return result

        def cache_clear():
            with master:
                l1.clear()
                key_locks.clear()

        def cache_info():
            with master:
                return {"name": name, "l1_size": len(l1), "maxsize": maxsize}

        wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
        wrapper.cache_info = cache_info  # type: ignore[attr-defined]
        wrapper.disk = disk  # type: ignore[attr-defined]
        return wrapper

    return decorator
