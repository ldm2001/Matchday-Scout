from typing import Protocol, Any


class Analyzer(Protocol):
    def data(self) -> Any:
        ...
