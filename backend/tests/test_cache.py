# layered_cache 데코레이터 단위 테스트 (Plan NFR-04: ≥6 케이스)
# - TC-01~TC-06: Design §9 시나리오
# - test_stable_key_format: 키 직렬화 형식 회귀 방어
import threading
import time
from pathlib import Path

from backend.services.core.cache import _stable_key, layered_cache


def test_stable_key_format():
    """_stable_key: simple 인자는 underscore join, 마지막 mark는 sha256[:12]"""
    key = _stable_key((1, 5, 3, ((1024, "abc"), (2048, "def"))))
    parts = key.split("_")
    assert parts[:3] == ["1", "5", "3"]
    assert len(parts[3]) == 12
    # 같은 args → 같은 key (재현성)
    assert _stable_key((1, 5, 3, ((1024, "abc"), (2048, "def")))) == key


def test_tc01_concurrent_same_key_single_call(tmp_path: Path):
    """TC-01: 동일 키 10 thread 동시 호출 시 fn은 1회만 실행"""
    call_count = {"n": 0}
    count_lock = threading.Lock()

    @layered_cache("tc01", base_dir=tmp_path)
    def slow_fn(x, mark):
        with count_lock:
            call_count["n"] += 1
        time.sleep(0.05)  # 다른 스레드가 master 잠금 경합에 도달할 시간 부여
        return x * 2

    results = [None] * 10
    threads = []

    def runner(i):
        results[i] = slow_fn(7, ("v1",))

    for i in range(10):
        t = threading.Thread(target=runner, args=(i,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    assert call_count["n"] == 1, f"fn 호출 1회 기대, 실제 {call_count['n']}회"
    assert all(r == 14 for r in results)


def test_tc02_l1_hit_skips_fn(tmp_path: Path):
    """TC-02: 같은 키 재호출은 L1 hit으로 fn 추가 호출 0회"""
    call_count = {"n": 0}

    @layered_cache("tc02", base_dir=tmp_path)
    def fn(x, mark):
        call_count["n"] += 1
        return x + 1

    for _ in range(5):
        assert fn(10, ("v1",)) == 11
    assert call_count["n"] == 1


def test_tc03_l1_evict_then_l2_hit(tmp_path: Path):
    """TC-03: L1 비운 뒤 재호출 시 L2 hit, fn 0회 추가 호출, L1 복구"""
    call_count = {"n": 0}

    @layered_cache("tc03", base_dir=tmp_path)
    def fn(x, mark):
        call_count["n"] += 1
        return x * 10

    fn(1, ("v1",))
    assert call_count["n"] == 1
    # L1만 강제로 비움 → L2(디스크) 파일은 그대로 유지
    fn.cache_clear()
    fn(1, ("v1",))
    assert call_count["n"] == 1  # L2 hit, 재계산 없음
    fn(1, ("v1",))
    assert call_count["n"] == 1  # 이제 L1 hit
    assert fn.cache_info()["l1_size"] == 1


def test_tc04_mark_change_new_key(tmp_path: Path):
    """TC-04: mark가 변경되면 새 키 → 새 계산. 구 mark는 별도 엔트리로 유지"""
    call_count = {"n": 0}

    @layered_cache("tc04", base_dir=tmp_path)
    def fn(x, mark):
        call_count["n"] += 1
        return x

    fn(1, ("v1",))
    fn(1, ("v2",))
    fn(1, ("v1",))  # L1 hit
    fn(1, ("v2",))  # L1 hit
    assert call_count["n"] == 2


def test_tc05_disk_corrupt_auto_unlink_recompute(tmp_path: Path):
    """TC-05: 디스크 파일 손상 시 DiskCache.get이 unlink + None 반환 → 재계산"""
    call_count = {"n": 0}

    @layered_cache("tc05", base_dir=tmp_path)
    def fn(x, mark):
        call_count["n"] += 1
        return x * 3

    fn(5, ("v1",))
    assert call_count["n"] == 1

    pkl_files = list(tmp_path.glob("tc05_*.pkl"))
    assert len(pkl_files) == 1
    pkl_files[0].write_bytes(b"\x00\x01\x02 corrupted pickle")
    fn.cache_clear()

    result = fn(5, ("v1",))
    assert result == 15
    assert call_count["n"] == 2


def test_tc06_maxsize_lru_evict_l2_preserved(tmp_path: Path):
    """TC-06: L1 maxsize 초과 시 LRU evict. L2는 보존되어 evict된 키 재호출 시 L2 hit"""
    call_count = {"n": 0}

    @layered_cache("tc06", maxsize=2, base_dir=tmp_path)
    def fn(x, mark):
        call_count["n"] += 1
        return x

    fn(1, ("v1",))  # L1=[1]
    fn(2, ("v1",))  # L1=[1,2]
    fn(3, ("v1",))  # L1=[2,3], 1은 L1에서 evict (L2는 보존)
    assert call_count["n"] == 3
    assert fn.cache_info()["l1_size"] == 2

    # 1을 다시 호출 → L1 miss → L2 hit → 재계산 없음
    fn(1, ("v1",))
    assert call_count["n"] == 3
