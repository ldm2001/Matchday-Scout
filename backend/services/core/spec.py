# 분석기 프로토콜 정의
from typing import Protocol, Any


# 분석기 인터페이스 - 모든 분석기가 구현해야 하는 data() 메서드 정의
class Analyzer(Protocol):
    def data(self) -> Any:
        ...
