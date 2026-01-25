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
class Overlay:
    actual_px: Dict[str, float]
    suggest_px: Dict[str, float]
    goal_px: Dict[str, float]
    angle: float
    quality: float


@dataclass
class HeatCell:
    row: int
    col: int
    value: float
    poly_px: List[Dict[str, float]]


@dataclass
class Heatmap:
    rows: int
    cols: int
    cells: List[HeatCell] = field(default_factory=list)
    suggest_cells: List[HeatCell] = field(default_factory=list)
    max: float = 0.0


@dataclass
class Moment:
    ts: float
    label: str
    actual: Dict[str, float]
    suggest: Dict[str, float]
    delta: float
    note: str
    conf: float
    overlay: Optional[Overlay] = None


@dataclass
class Report:
    job_id: str
    status: str
    clip: Clip
    moments: List[Moment] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    mode: str = "stub"
    heatmap: Optional[Heatmap] = None
