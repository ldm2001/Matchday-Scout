# 비디오 분석 데이터 모델 정의
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# 비디오 클립 정보 (URL, ID, 시작점, FPS 등)
@dataclass
class Clip:
    # 비디오 소스 URL 경로
    url: str
    # 메타정보에서 추출한 고유 비디오 ID
    video_id: str
    # 클립의 시작 시간 (초 단위, 기본값 0)
    start: int = 0
    # 비디오의 초당 프레임 생성 수 (FPS)
    fps: Optional[float] = None
    # 비디오 프레임 가로 해상도
    width: Optional[int] = None
    # 비디오 프레임 세로 해상도
    height: Optional[int] = None

# 오버레이 시각화 데이터 (실제/추천 위치, 골까지 각도)
@dataclass
class Overlay:
    # 선수의 실제 화면상 위치 (픽셀 좌표 기반)
    actual_px: Dict[str, float]
    # AI 전술 모델이 추천하는 화면상 위치 (픽셀)
    suggest_px: Dict[str, float]
    # 화면상 골대의 위치 타겟 좌표 (픽셀)
    goal_px: Dict[str, float]
    # 슛을 가정했을 때 골문과의 상대적 각도
    angle: float
    # 추출된 오버레이 상황에 대한 신뢰 품질 점수
    quality: float

# 히트맵 셀 데이터
@dataclass
class HeatCell:
    # 필드 그리드 상의 행 인덱스
    row: int
    # 필드 그리드 상의 열 인덱스
    col: int
    # 해당 셀 영역에서 발생한 이벤트 가치 산출값
    value: float
    # 화면에 셀 영역을 그리기 위한 다각형 꼭짓점 좌표들
    poly_px: List[Dict[str, float]]

# 히트맵 전체 데이터 (실제/추천 영역)
@dataclass
class Heatmap:
    # 분할된 그리드 맵의 전체 행 개수
    rows: int
    # 분할된 그리드 맵의 전체 열 개수
    cols: int
    # 필드 전역의 활동 셀 데이터 보관 리스트
    cells: List[HeatCell] = field(default_factory=list)
    # 전략적으로 추천/도달해야 하는 셀 데이터 리스트
    suggest_cells: List[HeatCell] = field(default_factory=list)
    # 히트맵 시각화를 위한 정규화용 최대 수치 기록
    max: float = 0.0

# 키 모멘트 데이터 (타임스탬프, 위치, 제안)
@dataclass
class Moment:
    # 모멘트가 발생한 시점의 영상 타임스탬프
    ts: float
    # 전술 상황을 묘사하는 모멘트 명칭 라벨 (예: 전환 속공)
    label: str
    # 실제 선수가 위치한 절대적인 마당 좌표 (Pitch 좌표)
    actual: Dict[str, float]
    # AI가 제안한 모멘트 내 이상적 선수 좌표 (Pitch 좌표)
    suggest: Dict[str, float]
    # 실제와 제안 위치 간의 기댓값 증감치 한도
    delta: float
    # 현재 모멘트에 부가적인 특징이나 코멘트 저장
    note: str
    # 현재 감지된 모멘트 상황에 대한 결과 신뢰도
    conf: float
    # 영상 시각화를 위해 매핑된 오버레이 데이터 객체
    overlay: Optional[Overlay] = None

# 분석 리포트 데이터 (클립, 모멘트, 히트맵)
@dataclass
class Report:
    # 사용자나 큐가 할당한 고유 분석 잡(Job) ID 
    job_id: str
    # 현재 리포트 생성 및 분석 진행 상태 문자열
    status: str
    # 원본 비디오 클립에 대한 기본 객체 정보
    clip: Clip
    # 영상에서 탐지해낸 주요 키 모멘트들의 리스트
    moments: List[Moment] = field(default_factory=list)
    # 분석 후 도출된 주요 요약 및 노티스 로그 보관
    notes: List[str] = field(default_factory=list)
    # 리포트 실행 방식이나 성격 모드 (기본은 stub)
    mode: str = "stub"
    # 영상 분석 완료 후 전역으로 생성된 히트맵 객체 정보
    heatmap: Optional[Heatmap] = None
