# 디스크 영속 캐시 - parquet/pickle을 atomic rename으로 저장하고 corrupt 시 자동 복구
from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any, Callable, Literal, Optional

import pandas as pd

_LOG = logging.getLogger(__name__)


# 내부 모듈에서만 직렬화 분기를 알고 외부는 단일 인터페이스로 다룸
class DiskCache:
    """파일명 규약: <base_dir>/<name>_<key>.<ext>
    - get/put은 예외를 삼키지 않고 WARNING으로 가시화한다
    - corrupt 파일을 만나면 unlink하여 다음 호출에서 재생성되도록 한다
    - purge는 caller가 keep 술어를 넘겨 정책을 직접 정한다 (singleton vs generation-grouped 양쪽 지원)
    """

    def __init__(
        self,
        name: str,
        serde: Literal["parquet", "pickle"],
        base_dir: Path,
    ) -> None:
        self.name = name
        self.serde = serde
        self.base_dir = base_dir
        self.ext = "parquet" if serde == "parquet" else "pkl"

    def _path(self, key: str) -> Path:
        return self.base_dir / f"{self.name}_{key}.{self.ext}"

    # 디스크에서 값 로드. 없거나 corrupt이면 None 반환 (corrupt는 자동 unlink)
    def get(self, key: str) -> Optional[Any]:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            if self.serde == "parquet":
                value = pd.read_parquet(path)
            else:
                with path.open("rb") as f:
                    value = pickle.load(f)
            _LOG.info("%s 캐시 적중: %s", self.name, path.name)
            return value
        except Exception as exc:
            _LOG.warning("%s 캐시 로드 실패 (%s): %s", self.name, path.name, exc)
            try:
                path.unlink()
            except OSError:
                pass
            return None

    # tmp 파일에 직렬화 후 atomic rename. 실패 시 tmp 정리하고 메모리 캐시는 그대로 유지
    def put(self, key: str, value: Any) -> None:
        tmp: Optional[Path] = None
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            path = self._path(key)
            tmp = path.with_suffix(f".{self.ext}.tmp")
            if self.serde == "parquet":
                value.to_parquet(tmp, index=False)
            else:
                with tmp.open("wb") as f:
                    pickle.dump(value, f, protocol=pickle.HIGHEST_PROTOCOL)
            tmp.replace(path)
            _LOG.info("%s 캐시 저장: %s", self.name, path.name)
        except Exception as exc:
            _LOG.warning("%s 캐시 저장 실패: %s", self.name, exc)
            if tmp is not None and tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    # keep 술어가 False를 반환하는 파일을 모두 unlink. caller가 정책(exact vs prefix)을 결정
    def purge(self, keep: Callable[[str], bool]) -> None:
        if not self.base_dir.exists():
            return
        prefix = f"{self.name}_"
        suffix = f".{self.ext}"
        for path in self.base_dir.glob(f"{self.name}_*{suffix}"):
            stem = path.name
            if not (stem.startswith(prefix) and stem.endswith(suffix)):
                continue
            key_part = stem[len(prefix): -len(suffix)]
            if not keep(key_part):
                try:
                    path.unlink()
                except OSError:
                    pass
