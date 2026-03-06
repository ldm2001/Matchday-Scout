# 분석기 추상 프로토콜 정의
from typing import Protocol, Any


# 시스템 내 모든 분석기(Analyzer) 클래스들이 의무적으로 구현해야 하는 명세
class Analyzer(Protocol):
    # 각 분석기는 고유 모직을 수행한 후 이 data() 메서드를 통해 최종 결과를 반환해야 함
    def data(self) -> Any:
        ...
