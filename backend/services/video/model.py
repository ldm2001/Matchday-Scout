# 비디오 분석 데이터 모델 정의
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# 비디오 클립 정보 (URL, ID, 시작점, FPS 등)
@dataclass
class Clip:
    url: str
    video_id: str
    start: int = 0
    fps: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None


# 오버레이 시각화 데이터 (실제/추천 위치, 골까지 각도)
@dataclass
class Overlay:
    actual_px: Dict[str, float]
    suggest_px: Dict[str, float]
    goal_px: Dict[str, float]
    angle: float
    quality: float


# 히트맵 셀 데이터
@dataclass
class HeatCell:
    row: int
    col: int
    value: float
    poly_px: List[Dict[str, float]]


# 히트맵 전체 데이터 (실제/추천 영역)
@dataclass
class Heatmap:
    rows: int
    cols: int
    cells: List[HeatCell] = field(default_factory=list)
    suggest_cells: List[HeatCell] = field(default_factory=list)
    max: float = 0.0


# 키 모멘트 데이터 (타임스탬프, 위치, 제안)
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


# 분석 리포트 데이터 (클립, 모멘트, 히트맵)
@dataclass
class Report:
    job_id: str
    status: str
    clip: Clip
    moments: List[Moment] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    mode: str = "stub"
    heatmap: Optional[Heatmap] = None
