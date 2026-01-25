from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Clip:
    url: str
    video_id: str
    start: int = 0
    fps: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None


@dataclass
class Moment:
    ts: float
    label: str
    actual: Dict[str, float]
    suggest: Dict[str, float]
    delta: float
    note: str
    conf: float


@dataclass
class Report:
    job_id: str
    status: str
    clip: Clip
    moments: List[Moment] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    mode: str = "stub"
