# OS 시스템 유틸리티 임포트
import os
import sys
from dataclasses import asdict
import importlib
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qs, urlparse
import math
import inspect
import numpy as np

# 필수 모듈을 안전하게 동적으로 임포트
def _opt_module(name: str) -> Any:
    try:
        # 지정된 이름의 모듈을 로드
        return importlib.import_module(name)
    except Exception:
        # 실패 시 None 반환
        return None

# 로드된 모듈 내의 특정 속성을 가져오는 헬퍼 함수
def _opt_attr(module_name: str, attr_name: str) -> Any:
    # 모듈 로드
    mod = _opt_module(module_name)
    if mod is None:
        return None
    # 속성 추출 및 반환
    return getattr(mod, attr_name, None)

# 주요 외부 라이브러리 동적 로딩
cv2 = _opt_module("cv2")
YoutubeDL = _opt_attr("yt_dlp", "YoutubeDL")
YOLO = _opt_attr("ultralytics", "YOLO")
torch = _opt_module("torch")

# 데이터 모델 클래스들 임포트
from .model import Clip, HeatCell, Heatmap, Moment, Overlay, Report

# 루트 경로 계산 및 캐시 디렉토리 설정
ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "cache" / "video"
CACHE.mkdir(parents=True, exist_ok=True)

# 시뮬레이션 및 모델 환경 변수 상수 설정
MAX_SEC = 90
STEP_SEC = 0.5
MAX_SAMPLES = 180
MIN_CONF = 0.15
MODEL = None
HEAT_ROWS = 12
HEAT_COLS = 16
# YOLO 모델 클래스 ID (32: Sports ball, 0: Person)
BALL_CLASS = 32
PLAYER_CLASS = 0

# torch 안전 로드 허용 (보안 취약점 방지)
def _torch_safe() -> None:
    # torch가 로드되지 않았다면 종료
    if torch is None:
        return
    # torch 직렬화 모듈 확인
    serial = getattr(torch, "serialization", None)
    if serial is None:
        return
    # add_safe_globals 함수 확인
    add = getattr(serial, "add_safe_globals", None)
    if add is None:
        return
    try:
        # ultralytics 모델 관련 클래스 임포트 시도
        tasks_mod = importlib.import_module("ultralytics.nn.tasks")
        nn = importlib.import_module("torch.nn")
        detect_model = getattr(tasks_mod, "DetectionModel", None)
    except Exception:
        return
    if detect_model is None:
        return
    extra = []
    extra_nn = []
    try:
        # ultralytics.nn.modules 내의 모든 커스텀 클래스 추출
        u = importlib.import_module("ultralytics.nn.modules")
        extra = [obj for _, obj in vars(u).items() if inspect.isclass(obj)]
    except Exception:
        extra = []
    try:
        # torch.nn 내의 모든 커스텀 클래스 추출
        extra_nn = [obj for _, obj in vars(nn).items() if inspect.isclass(obj)]
    except Exception:
        extra_nn = []
    try:
        # 모든 클래스를 안전 목록에 등록하여 피클(pickle) 역직렬화 보안 강화
        add([detect_model, *extra, *extra_nn])
    except Exception:
        return

# macOS 로컬 디렉토리에서 웹 브라우저 쿠키 프로필 탐색
def _profile_hint(browser: str) -> str | None:
    # 운영체제가 mac이 아닐 경우 None 반환
    if sys.platform != "darwin":
        return None
    base = None
    # 각 브라우저의 사용자 데이터 기본 경로 할당
    if browser == "chrome":
        base = Path.home() / "Library/Application Support/Google/Chrome"
    elif browser == "edge":
        base = Path.home() / "Library/Application Support/Microsoft Edge"
    elif browser == "brave":
        base = Path.home() / "Library/Application Support/BraveSoftware/Brave-Browser"
    # 해당 브라우저의 설정 폴더가 존재하지 않을 경우 종료
    if not base or not base.exists():
        return None
    picks = []
    # 기본 "Default" 프로필과 "Profile N" 형태의 프로필 명을 모두 수집
    names = ["Default"]
    names.extend([p.name for p in base.glob("Profile *")])
    for name in names:
        # 각 프로필 폴더 안의 Cookies 파일 확인
        cookie = base / name / "Cookies"
        if cookie.exists():
            # 사용 가능 쿠키를 추출해 최근 수정 일자와 함께 수집
            picks.append((name, cookie.stat().st_mtime))
    if not picks:
        return None
    # 최근 접속한 브라우저 프로필을 1순위로 사용하기 위해 최신순 정렬
    picks.sort(key=lambda x: x[1], reverse=True)
    # 가장 먼저 나오는 프로필 이름 반환
    return picks[0][0]

# 문자열로 된 포맷(예: 1h 30m)을 초 단위 정수로 환산
def _sec(val: str) -> int:
    # 비어있는 값이면 0 반환
    if not val:
        return 0
    raw = val.strip()
    # 문자열이 모두 숫자면 즉시 정수로 반환
    if raw.isdigit():
        return int(raw)
    total = 0
    buf = ""
    # "1h2m3s" 문자열을 한 글자씩 순회하며 h, m, s 단위로 변환 처리
    for ch in raw:
        if ch.isdigit():
            # 숫자일 경우 버퍼에 추가
            buf += ch
            continue
        # 문자가 나올 때 이전 버퍼가 없다면 스킵
        if not buf:
            continue
        num = int(buf)
        # 각 문자에 해당하는 초 기준을 더하기 (시간은 3600, 분은 60)
        if ch == "h":
            total += num * 3600
        elif ch == "m":
            total += num * 60
        elif ch == "s":
            total += num
        # 숫자 버퍼 비우기
        buf = ""
    # 남아있는 숫자가 더 있다면 마지막 초에 누적해주기
    if buf:
        total += int(buf)
    return total

# 유튜브 URL 환경에서 비디오 ID와 영상 재생 시작 부분 추출
def _vid_id(url: str) -> Tuple[str, int]:
    # 비어있는 URL 처리
    if not url:
        return "", 0
    # URL 파싱 모델로 구조 분해
    info = urlparse(url)
    host = info.netloc.lower()
    path = info.path.strip("/")
    qs = parse_qs(info.query)
    vid = ""
    # 호스트를 기반으로 동영상 ID 찾기
    if "youtu.be" in host:
        # 단축 URL의 경우 바로 뒷단이 키가 됨
        vid = path.split("/")[0]
    elif "youtube.com" in host:
        # 오리지널 URL은 v 쿼리스트링에서 가져옴
        if path.startswith("watch"):
            vid = qs.get("v", [""])[0]
        # 짧은 영상의 하위 도메인 처리
        elif path.startswith("shorts/"):
            vid = path.split("/")[1] if "/" in path else ""
        # 임베드 형태의 URL 추출
        elif path.startswith("embed/"):
            vid = path.split("/")[1] if "/" in path else ""
    # t 파라미터나 start 쿼리에서 시작점 시간대(초) 확보
    start = _sec(qs.get("t", qs.get("start", ["0"]))[0])
    # 고유 ID와 시작 초 단위 반환
    return vid, start

# 로컬 비디오 파일 경로를 바탕으로 Clip 메타 객체(FPS, 해상도 등)를 생성하는 함수
def _clip_path(path: Path) -> Clip:
    # opencv 모듈이 로드되지 않았다면 분석이 불가하므로 예외 발생
    if cv2 is None:
        raise RuntimeError("opencv missing")
    # OpenCV 비디오 캡처 객체 로드
    cap = cv2.VideoCapture(str(path))
    # 비디오 프로퍼티에서 FPS 추출 (정보가 없으면 25.0 기본값 적용)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    # 비디오 가로 해상도 추출 (정수형 변환)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    # 비디오 세로 해상도 추출 (정수형 변환)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    # 메모리 누수 방지를 위한 비디오 캡처 객체 릴리즈
    cap.release()
    # 확장자를 제외한 순수 파일명을 비디오 고유 ID로 할당
    name = path.stem
    # 최종 추출된 메타 스펙을 모은 Clip 객체 반환
    return Clip(url=str(path), video_id=name, start=0, fps=fps, width=width, height=height)

# 전역 YOLO 객체 감지 모델을 로드하고 인스턴스를 반환하는 함수 (싱글톤 패턴)
def _model() -> Any:
    # 전역에 선언된 MODEL 변수 참조
    global MODEL
    # 모델이 아직 로드되지 않은 상태라면 초기화 수행
    if MODEL is None:
        # YOLO 패키지가 없다면 예외 발생
        if YOLO is None:
            raise RuntimeError("ultralytics missing")
        # 모델 로드 전 PyTorch의 안전한 역직렬화를 위한 클래스 등록 함수 호출
        _torch_safe()
        # yolov8 nano 버전의 사전 학습된 모델 로드
        MODEL = YOLO("yolov8n.pt")
    # 메모리에 얹어진 완성된 모델 객체 반환
    return MODEL

# 영상 프레임 내에서 축구장 잔디색(그린) 매트릭스를 찾기 위해 HSV 마스크를 생성하는 함수
def _mask(frame: np.ndarray) -> np.ndarray:
    # 기본 BGR 이미지를 색조 판별이 용이한 HSV 색상 공간으로 변환
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    # 잔디 색의 최저 임계값 어레이 지정 (색조 35 부근)
    lower = np.array([35, 35, 35])
    # 잔디 색의 최고 임계값 어레이 지정 (색조 85 부근)
    upper = np.array([85, 255, 255])
    # 지정한 범위 내에 드는 픽셀만 255(흰색)로 추출하는 이진화 마스크 생성
    mask = cv2.inRange(hsv, lower, upper)
    # 모폴로지 연산을 위한 5x5 단위의 모든 값이 1인 사각형 커널 생성
    kernel = np.ones((5, 5), np.uint8)
    # 열기(Open) 연산으로 자잘한 외곽 노이즈 픽셀 제거
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    # 닫기(Close) 연산으로 마스크 영역 내부의 비어있는 구멍 메우기
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    # 최종 정제된 잔디 영역 마스크 맵 반환
    return mask

# 무작위 순서인 4개의 코너 포인트를 정해진 모서리 순서(좌상, 우상, 우하, 좌하)로 정렬하는 함수
def _box(pts: np.ndarray) -> np.ndarray:
    # 4개 좌표들의 각각의 x좌표와 y좌표의 합 계산
    total = pts.sum(axis=1)
    # 4개 좌표들의 x좌표와 y좌표 간의 차이 계산
    diff = np.diff(pts, axis=1).reshape(-1)
    # 합이 가장 작은 지점은 좌표상의 좌상단(Top-Left)
    tl = pts[np.argmin(total)]
    # 합이 가장 큰 지점은 좌표상의 우하단(Bottom-Right)
    br = pts[np.argmax(total)]
    # 차이가 가장 작은 지점은 좌표상의 우상단(Top-Right)
    tr = pts[np.argmin(diff)]
    # 차이가 가장 큰 지점은 좌표상의 좌하단(Bottom-Left)
    bl = pts[np.argmax(diff)]
    # 계산된 순서대로 패킹 후 다차원 Float 배열 형태로 반환
    return np.array([tl, tr, br, bl], dtype=np.float32)

# 퍼스펙티브 변환 매트릭스를 통해 프레임 내 특정 지점 좌표를 2D 마당 좌표(Pitch)로 매핑하는 함수
def _pitch(pt: np.ndarray, mat: np.ndarray) -> np.ndarray:
    # cv2.perspectiveTransform 규격에 맞게 3차원 배열 형태로 원본 좌표 패킹
    pack = np.array([[pt]], dtype=np.float32)
    # 캘리브레이션된 매트릭스 정보를 기반으로 좌표 투영 변환
    out = cv2.perspectiveTransform(pack, mat)
    # 래핑된 차원을 한 꺼풀 벗겨내고 최종 2D (x, y) 좌표 어레이만 리턴
    return out[0][0]

# 입력된 스칼라 값이 low 최소치와 high 최대치 스케일 내부를 벗어나지 않도록 값을 깎아주는 헬퍼 함수
def _clip(val: float, low: float, high: float) -> float:
    # min과 max 조합으로 경계 내부로 클램핑 처리
    return float(max(low, min(high, val)))

# 주어진 크기와 스케일 기준에 맞춰 상대 위치를 0.0과 scale 사이로 비례 정규화하는 함수
def _norm(val: float, size: float, scale: float) -> float:
    # 화면 크기가 0이하라면 비율 산정이 불가능해 0 반환
    if size <= 0:
        return 0.0
    # 값의 상대적 비율을 구한 뒤 스케일을 곱하고, 범위를 넘어가지 않게 클립핑
    return _clip(val / size * scale, 0.0, scale)

# 역변환 매트릭스를 활용해 논리적인 2D 마당(Pitch) 좌표를 다시 영상 픽셀 좌표계로 되돌리는 함수
def _pitch_px(pt: Tuple[float, float], inv: np.ndarray | None, clip: Clip) -> Tuple[float, float]:
    # opencv가 켜져있고 역변환 행렬이 유효한 실전 케이스일 때
    if cv2 is not None and inv is not None:
        # 역변환을 위한 3차원 형태 패킹
        pack = np.array([[pt]], dtype=np.float32)
        # 역행렬로 좌표점 투영
        out = cv2.perspectiveTransform(pack, inv)
        # 추출된 원본 영상 픽셀의 절대 x, y값 반환
        return float(out[0][0][0]), float(out[0][0][1])
    # 매트릭스가 없는 상태면 Clip에 들어있는 비디오 비율 기반 단순 비례 투영 시도
    width = clip.width or 0
    height = clip.height or 0
    # 비디오 크기 정보조차 없으면 픽셀 투영을 포기하고 초기 좌표 반환
    if width <= 0 or height <= 0:
        return 0.0, 0.0
    # x루트는 길이 105 기준, y루트는 길이 68 기준으로 화면 크기에 곱해 비율적 추정치 반환
    return float(pt[0] / 105.0 * width), float(pt[1] / 68.0 * height)

# 105x68 크기의 경기장에서 x, y 마당 좌표가 특정 크기의 행/열 그리드 중 어디에 속하는지 인덱싱
def _grid_idx(x: float, y: float, rows: int, cols: int) -> Tuple[int, int]:
    # x값을 가로 길이 105로 나눠 비율을 구하고 전체 열수를 곱해 인덱스 산정 후 클립핑
    col = int(_clip(x / 105.0 * cols, 0, cols - 1))
    # y값을 세로 길이 68로 나눠 비율을 구하고 전체 행수를 곱해 인덱스 산정 후 클립핑
    row = int(_clip(y / 68.0 * rows, 0, rows - 1))
    # 계산된 로우 및 칼럼 인덱스 반환
    return row, col

# 히트맵 수치 그리드 2차원 배열과 역변환 행렬을 입력받아 프론트 시각화용 다각형 픽셀 리스트로 가공
def _heat_cells(grid: List[List[float]], inv: np.ndarray | None, clip: Clip) -> List[HeatCell]:
    # 생성된 HeatCell을 담아둘 리스트 컨테이너
    cells: List[HeatCell] = []
    # 입력된 그리드의 전체 행 길이 추출
    rows = len(grid)
    # 첫번째 행의 길이를 전체 열의 길이로 추출 (배열이 비어있으면 0)
    cols = len(grid[0]) if rows else 0
    # 위에서 아래로 행 단위 순회
    for row in range(rows):
        # 좌에서 우로 열 단위 순회
        for col in range(cols):
            # 현재 셀 영역의 좌측 마당 좌표 (0 ~ 105 기반)
            x0 = col / cols * 105.0
            # 현재 셀 영역의 우측 마당 좌표
            x1 = (col + 1) / cols * 105.0
            # 현재 셀 영역의 상단 마당 좌표 (0 ~ 68 기반)
            y0 = row / rows * 68.0
            # 현재 셀 영역의 하단 마당 좌표
            y1 = (row + 1) / rows * 68.0
            # 위에서 구한 논리 좌표 꼭지점 4개를 실제 화면의 픽셀 좌표로 투영 변환
            p1 = _pitch_px((x0, y0), inv, clip)
            p2 = _pitch_px((x1, y0), inv, clip)
            p3 = _pitch_px((x1, y1), inv, clip)
            p4 = _pitch_px((x0, y1), inv, clip)
            # 변환된 정보들을 기반으로 HeatCell 객체 조립 후 리스트 추가
            cells.append(
                HeatCell(
                    row=row,
                    col=col,
                    value=float(grid[row][col]),
                    poly_px=[
                        {"x": p1[0], "y": p1[1]},
                        {"x": p2[0], "y": p2[1]},
                        {"x": p3[0], "y": p3[1]},
                        {"x": p4[0], "y": p4[1]},
                    ],
                )
            )
    # 완성된 전체 그리드 셀 구성 정보 배열 리턴
    return cells

# 특정 좌표에서 양쪽 골포스트를 바라볼 때 형성되는 슈팅 유효 각도를 계산
def _shot_angle(x: float, y: float) -> float:
    # 공격 방향의 좌측 골포스트 목표 좌표 (중앙 34 기준으로 상하 3.66 거리)
    left = (105.0, 34.0 - 3.66)
    # 공격 방향의 우측 골포스트 목표 좌표
    right = (105.0, 34.0 + 3.66)
    # 현재 위치에서 좌측 골대까지의 2D 벡터 산출
    v1 = (left[0] - x, left[1] - y)
    # 현재 위치에서 우측 골대까지의 2D 벡터 산출
    v2 = (right[0] - x, right[1] - y)
    # 두 벡터의 길이를 각각 구해 내적을 위한 분모 수치 생성
    denom = math.hypot(*v1) * math.hypot(*v2)
    # 거리가 0이하라면 각도는 0 반환
    if denom <= 0:
        return 0.0
    # 두 벡터의 내적(Dot Product) 값 계산
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    # 도트 결과를 길이 곱으로 나누어 Cosine 세타 값을 구하고 유효 범위(-1~1) 클립핑
    cosv = max(-1.0, min(1.0, dot / denom))
    # 도출된 코사인 값을 아크코사인 하여 각도(Degree)로 변환 후 리턴
    return math.degrees(math.acos(cosv))

# 가로 길이 x 기준 선수의 종방향 구역(Lane) 판별
def _lane(x: float) -> str:
    # 88m 넘은 완전히 골대 쪽 영역
    if x >= 88.0:
        return "박스 안"
    # 80~88m 사이 진입 영역
    if x >= 80.0:
        return "박스 근처"
    # 그 외 미들 서드/수비 서드 등
    return "중앙 지역"

# 세로 길이 y 기준 선수의 횡방향 구역(Zone) 판별
def _zone(y: float) -> str:
    # 22.5m 보다 작은 좌측
    if y < 22.5:
        return "좌측"
    # 45.5m 보다 큰 우측
    if y > 45.5:
        return "우측"
    # 그 사이 중앙 영역
    return "중앙"

# 거리와 슈팅 각도에 기반해 xG와 유사한 추정 슈팅 가능 가치(확률) 산출
def _shot_value(dist: float, angle: float) -> float:
    # 거리에 따른 로지스틱 함수 감쇠항 계산 (거리가 멀수록 패널티)
    dist_term = 1.0 / (1.0 + math.exp((dist - 18.0) / 5.5))
    # 각도에 따른 로지스틱 함수 감쇠항 계산 (각도가 좁을수록 패널티)
    angle_term = 1.0 / (1.0 + math.exp(-(angle - 14.0) / 5.0))
    # 고정 보정치(0.05)와 거리/각도 가중치를 합산해 확률 가치 도출
    raw = 0.05 + 0.75 * dist_term + 0.2 * angle_term
    # 결과값이 0.98(98%)을 넘지 않게 조절하여 반환
    return _clip(raw, 0.0, 0.98)

# 추출된 움직임에 대한 위치, 도달 거리, 속도 등을 고려하여 플레이 상황 라벨 할당
def _moment_label(
    x: float,
    y: float,
    dist: float,
    angle: float,
    vx: float,
    vy: float,
) -> str:
    # 좌표 이동 속도 총합(유클리드)
    speed = math.hypot(vx, vy)
    # 골대 중앙(105, 34)까지의 남은 x, y 축 거리
    to_goal_x = 105.0 - x
    to_goal_y = 34.0 - y
    # 골대까지의 직선 잔여 거리 길이
    goal_norm = max(1e-6, math.hypot(to_goal_x, to_goal_y))
    # 골문 방향으로 향하는 이동 벡터와 축 거리 벡터를 내적하여 진척 속도 도출
    toward_goal = (vx * to_goal_x + vy * to_goal_y) / goal_norm
    # 세로 34선을 기준으로 상하 방향으로 벌어진 간극
    center_gap = abs(y - 34.0)
    # y축 기준 좌우 횡방향 절댓값 횡속도
    lateral_speed = abs(vy)

    # 13.5m 안쪽 거리에 유효 각도가 확보된 상황
    if dist <= 13.5 and angle >= 15.0:
        return "골문 정면 결정 찬스"
    # 상당히 깊이 파고들었고, 측면으로 많이 벌려진 형태
    if x >= 96.0 and center_gap >= 10.0:
        return "바이라인 침투"
    # 깊고 중앙에 가까우면서 지속적으로 골문을 향하는 스프린트
    if x >= 90.0 and center_gap <= 9.0 and toward_goal >= 2.0:
        return "컷백 유도 침투"
    # 하프스페이스(Zone 14 주변 측면부)로 진입한 형태
    if x >= 84.0 and center_gap >= 11.0:
        return "하프스페이스 파고듦"
    # 거리가 다소 있지만 슈팅을 위한 정면 위치로의 접근
    if dist <= 28.0 and angle < 10.0:
        return "박스 외곽 슈팅 준비"
    # 골문 쪽으로 강력하고 빠른 속도로 전진하는 역습형 패스/드리블
    if speed >= 5.0 and toward_goal >= 2.5:
        return "전환 속공 전개"
    # 속도의 대부분을 횡이동에 소비하면서 반대 측면으로 넘어가는 흐름
    if lateral_speed >= max(2.2, speed * 0.58) and x >= 60.0:
        return "측면 스위치 전개"
    # 중앙선 밑에서 시작하며 압박을 벗어나 공을 전방에 돌려주는 흐름
    if x < 62.0 and toward_goal >= 2.0 and speed >= 3.5:
        return "압박 회피 전진"
    # 하프라인 밑에서 느린 국면의 백패스나 스리백 후방 빌드업
    if speed < 1.2 and x < 70.0:
        return "점유 안정 빌드업"
    # 박스 내외곽 지역 안착
    if x >= 88.0:
        return "박스 진입"
    # 파이널 서드 주변 도달
    if x >= 74.0:
        return "공격 전개"
    # 기본 디폴트 라벨 반환
    return "중원 전진 빌드업"

def _tempo_note(x: float, y: float, vx: float, vy: float) -> str:
    speed = math.hypot(vx, vy)
    to_goal_x = 105.0 - x
    to_goal_y = 34.0 - y
    goal_norm = max(1e-6, math.hypot(to_goal_x, to_goal_y))
    toward_goal = (vx * to_goal_x + vy * to_goal_y) / goal_norm
    if speed >= 6.0:
        tempo = "고속"
    elif speed >= 3.0:
        tempo = "중속"
    else:
        tempo = "저속"
    if toward_goal >= 3.2:
        drive = "직선 침투"
    elif toward_goal >= 1.2:
        drive = "전진 유지"
    elif toward_goal <= -0.6:
        drive = "리사이클"
    else:
        drive = "횡전개"
    side = "중앙"
    if y < 22.5:
        side = "좌"
    elif y > 45.5:
        side = "우"
    return f"{tempo} 템포 · {side} {drive}"


# 객체의 최근 N개 프레임 이동 경로를 토대로 흔들림 현상을 보정(스무딩) 처리하는 함수
def _smooth_points(points: List[Dict], window: int = 2) -> List[Dict]:
    # 포인트 개수가 너무 적으면 보정 없이 그대로 리턴
    if len(points) < 3:
        return points
    # 스무딩 처리된 좌표들을 담을 리스트
    smooth: List[Dict] = []
    # 포인트 배열의 전체 길이
    size = len(points)
    # 각 포인트를 순회하며 앞뒤 프레임 정보 통합
    for idx, item in enumerate(points):
        x_acc = 0.0
        y_acc = 0.0
        w_acc = 0.0
        # 블렌딩할 윈도우 슬라이드의 좌측(과거) 범위 설정
        left = max(0, idx - window)
        # 윈도우 슬라이드의 우측(미래) 범위 설정
        right = min(size, idx + window + 1)
        # 좌우 범위 안의 근접 픽셀들을 돌면서 가중 평균 산출
        for pos in range(left, right):
            peer = points[pos]
            # 현재 프레임과의 시간/인덱스 차이(도약) 계산
            hop = abs(pos - idx)
            # 프레임이 멀어질수록 가중해 떨어뜨림 (거리 감쇠)
            dist_w = 1.0 / (1.0 + hop)
            # YOLO 감지 신뢰도(Confidence) 반영 (최소 0.05 부여)
            conf_w = max(0.05, float(peer.get("conf", 0.1)))
            # 거리 가중치와 화질 가중치 곱셉하여 최종 가중치 도출
            w = dist_w * conf_w
            # x좌표 가중치 누적 적용
            x_acc += float(peer["x"]) * w
            # y좌표 가중치 누적 적용
            y_acc += float(peer["y"]) * w
            # 가중치의 총합 계산
            w_acc += w
        # 가중치 합이 0 이하라면 원본 좌표 그대로 승계
        if w_acc <= 0:
            smooth.append(item.copy())
            continue
        # 가중치로 나눠주어 현재 프레임의 추정 중앙(Target) 좌표 산정
        target_x = x_acc / w_acc
        target_y = y_acc / w_acc
        # 블렌딩 비율 결정: 배열 양끝단에선 원본 중심(0.28), 중앙일수록 부드럽게(0.62)
        blend = 0.62 if 0 < idx < size - 1 else 0.28
        # 계산된 타겟 좌표와 원본 좌표를 블렌딩하여 새 딕셔너리로 추가
        smooth.append({
            **item,
            "x": float(item["x"]) * (1.0 - blend) + target_x * blend,
            "y": float(item["y"]) * (1.0 - blend) + target_y * blend,
        })
    # 스무딩 이후 물리적으로 불가능한 속도의 순간이동(Jump)을 후처리 필터링
    for idx in range(1, len(smooth)):
        # 직전 프레임 포인트 참조
        prev = smooth[idx - 1]
        # 현재 프레임 포인트 참조
        cur = smooth[idx]
        # 타임스탬프 상의 시간 경과량 계산(최소 0.2초 설정)
        dt = max(0.2, float(cur["ts"]) - float(prev["ts"]))
        # 해당 시간 동안 움직일 수 있는 최대 이동 폭(물리적 속도 한계) 도출
        max_step = 18.0 * dt + 0.8
        # x축 방향 델타
        dx = float(cur["x"]) - float(prev["x"])
        # y축 방향 델타
        dy = float(cur["y"]) - float(prev["y"])
        # 현재 두 포인트 사이의 유클리디안 물리 거리 산출
        dist = math.hypot(dx, dy)
        # 이동거리가 최대 허용치를 초과했다면
        if dist > max_step and dist > 0:
            # 최대 허용치를 실제 거리로 나눈 조정 비율 산출
            ratio = max_step / dist
            # 비율에 맞춰 현재 위치를 강제 축소/수정 적용
            cur["x"] = float(prev["x"]) + dx * ratio
            cur["y"] = float(prev["y"]) + dy * ratio
    # 스무딩 및 아웃라이어가 제거된 좌표 리스트 반환
    return smooth

# 1단계: 외부 링크/파일을 열어 기본 비디오 속성을 로드하는 클래스
class Link:
    # 모듈 간 데이터 버스에서 식별할 키워드
    key = "link"

    # 파이프라인 워크플로우를 처리하는 주 진입점 함수 (context 패스스루 방식)
    def unit(self, ctx: Dict) -> Dict:
        # 유튜브 로더가 없다면 런타임 종료
        if YoutubeDL is None:
            raise RuntimeError("yt_dlp missing")
        # 요청 컨텍스트 내에 로컬 파일 경로가 배정된 경우
        if ctx.get("file_path"):
            # 경로 절대/유효경로 확인 및 파싱
            path = Path(ctx["file_path"]).expanduser().resolve()
            # 파일이 시스템 상에 없으면 오류
            if not path.exists():
                raise RuntimeError("file missing")
            # 추후 프로세싱에서 쓸 수 있게 파일 경로 저장
            ctx["path"] = path
            # Clip 객체 정보 빌드 후 컨텍스트 탑재
            ctx["clip"] = _clip_path(path)
            # 노트 정보 추가
            ctx["notes"].append("file_ok")
            return ctx
        # 외부 URL인 경우 URL 획득
        url = ctx["url"]
        # 유튜브 URL에서 고유 ID 및 시작 초 파싱
        vid, start = _vid_id(url)
        # ID 추출에 실패했을경우 경고 추가
        if not vid:
            ctx["notes"].append("video_id_missing")
        # yt_dlp를 활용한 mp4 출력 영상 저장 위치 문자열 확보
        out = str(CACHE / "%(id)s.%(ext)s")
        # yt_dlp 구동 옵션 구성 세팅
        opts = {
            "outtmpl": out,
            "format": "mp4/best",
            "quiet": True, # 출력 로그 숨김 처리
            "noplaylist": True, # 플레이리스트 전체 다운로드 방지
        }
        # 환경 변수에서 별도 넷스케이프 텍스트/쿠키 파일 설정 확인
        cookie_file = os.getenv("VIDEO_COOKIE_FILE")
        if cookie_file:
            opts["cookiefile"] = cookie_file
            ctx["notes"].append("cookie_file")
        # 환경 변수를 통한 웹 브라우저 종류/프로필 정보 확인
        browser = os.getenv("VIDEO_COOKIE_BROWSER")
        profile = os.getenv("VIDEO_COOKIE_PROFILE")
        # macOS의 경우 기본으로 크롬 브라우저 캐치 시도
        if not browser and sys.platform == "darwin":
            browser = "chrome"
        # 브라우저만 알려졌고 프로필이 없다면 동적으로 힌트 추출
        if browser and not profile:
            profile = _profile_hint(browser)
        # 사용 가능한 브라우저 정보가 있다면
        if browser:
            # 쿠키 탈취를 위한 yt 옵션 인자 세팅 옵션화
            opts["cookiesfrombrowser"] = (browser, profile) if profile else (browser,)
            ctx["notes"].append(f"cookie_{browser}")
            # 적용된 프로필 정보 로그화
            if profile:
                ctx["notes"].append(f"profile_{profile}")
        # 세팅된 옵션으로 yt_dlp 인스턴스 오픈 컨텍스트 블록
        with YoutubeDL(opts) as ydl:
            # 영상 다운로드 실행 및 메타 데이터 정보 파악 대기
            info = ydl.extract_info(url, download=True)
            # 최종 다운로드 완료된 대상 mp4 경로 문자열 반환
            path = Path(ydl.prepare_filename(info))
        # 파싱 오류 감지를 위한 cv2 존재 확인
        if cv2 is None:
            raise RuntimeError("opencv missing")
        # 외부에서 다운받은 영상 캡처 준비
        cap = cv2.VideoCapture(str(path))
        # 기본 메타 정보/FPS 추출
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        # 화면의 가로 폭
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        # 화면의 세로 폭
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        # 캡처 객체 정리
        cap.release()
        # 프로세스 상에 공유할 로컬 영상 절대 경로 유지
        ctx["path"] = path
        # 다운받은 영상을 기반으로 종합된 Clip 파이프라인 변수 저장
        ctx["clip"] = Clip(url=url, video_id=vid, start=start, fps=fps, width=width, height=height) # Clip 저장
        # 파이프라인 성공 노트 추가
        ctx["notes"].append("link_ok")
        # 데이터가 보충된 원본 컨텍스트 객체 스택 상향 리턴
        return ctx


# 2단계: 영상 프레임 분석을 통해 마당(Pitch) 캘리브레이션 행렬 도출
class Calib:
    # 파이프라인 딕셔너리에 탑재될 키워드 문자열
    key = "calib"

    # 칼리브레이션 모듈의 주 실행 단위 함수
    def unit(self, ctx: Dict) -> Dict:
        # OpenCV 라이브러리가 없다면 분석 불가능
        if cv2 is None:
            raise RuntimeError("opencv missing")
        # 컨텍스트에서 이전 단계가 마련해둔 영상 경로 추출
        path = ctx["path"]
        # Clip 객체에 기록된 사용자/영상 기본 시작 지점 시간 로드
        start = ctx["clip"].start
        # 영상 파일 열기
        cap = cv2.VideoCapture(str(path))
        # 시작 시점으로 재생 포인트 점프(밀리초 기준)
        cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
        # 해당 프레임의 이미지를 한 장 읽어오기
        ok, frame = cap.read()
        cap.release()
        # 프레임 캡처에 실패했다면 캘리브레이션 건너뛰기
        if not ok:
            ctx["calib"] = {"mat": None, "quality": 0.0}
            ctx["notes"].append("calib_skip")
            return ctx
        # _mask 헬퍼를 사용해 초록색 잔디 영역만 255로 이진화 추출
        mask = _mask(frame)
        # 흰색 영역(잔디) 면적 픽셀 개수 합계 산출
        area = float(mask.sum()) / 255.0
        # 화면의 총 픽셀 개수 
        total = frame.shape[0] * frame.shape[1]
        # 전체 화면 중 잔디 영역이 차지하는 비율 계산
        ratio = area / total if total else 0.0
        # 잔디 영역(mask)의 가장자리 윤곽선(Contour) 검출 수집
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # 추출된 윤곽선이 전무하다면 캘리브레이션 불가 처리
        if not cnts:
            ctx["calib"] = {"mat": None, "quality": 0.0}
            ctx["notes"].append("calib_none")
            return ctx
        # 발견된 윤곽선 중 가장 면적이 큰 형태 1개(주 경기장 영역) 채택
        top = max(cnts, key=cv2.contourArea)
        # 해당 외곽선을 감싸는 최소 영역의 임의각도 사각형 구획
        rect = cv2.minAreaRect(top)
        # 사각형의 꼭지점 모서리 좌표 4개 추출
        box = cv2.boxPoints(rect)
        # 추출된 4개의 화면상 좌표 포인트를 좌상,우상,우하,좌하 순으로 정렬 (소스 영역)
        src = _box(np.array(box, dtype=np.float32))
        # 실제 축구 마당(105x68 규격)의 타겟 목적지 꼭지점 좌표 설정 (데스티네이션 영역)
        dst = np.array([[0, 0], [105, 0], [105, 68], [0, 68]], dtype=np.float32)
        # 픽셀 좌표(src)를 마당 논리 좌표(dst)로 변환해주는 호모그래피 행렬 도출
        mat = cv2.getPerspectiveTransform(src, dst)
        # 논리 마당 좌표를 역으로 화면 픽셀 위치로 돌려줄 역행렬 계산
        inv = cv2.getPerspectiveTransform(dst, src)
        # 화면 내 잔디 비율을 기반으로 칼리브레이션 정확도 추론 (마당 면적이 넓을수록 정밀함)
        quality = _clip(ratio * 1.6, 0.0, 1.0)
        # 도출된 매트릭스와 품질 점수를 칼리브레이션 객체에 탑재
        ctx["calib"] = {"mat": mat, "inv": inv, "quality": quality}
        ctx["notes"].append(f"calib_{quality:.2f}")
        return ctx

# 3단계: 확보된 비디오를 통해 프레임별 타겟(공, 선수) 좌표를 추적
class Track:
    # 파이프라인 딕셔너리에 탑재될 키워드 문자열
    key = "track"

    # 트래킹 모듈의 주 실행 단위 함수
    def unit(self, ctx: Dict) -> Dict:
        # OpenCV 라이브러리가 없다면 분석 불가능
        if cv2 is None:
            raise RuntimeError("opencv missing")
        # 컨텍스트 보관 영상 경로 추출
        path = ctx["path"]
        # 컨텍스트 보관 원본 영상 속성 추출
        clip = ctx["clip"]
        # 캘리브레이션 딕셔너리 정보 가져오기
        calib = ctx.get("calib", {})
        # 퍼스펙티브 변환 정방 매트릭스 추출
        mat = calib.get("mat")
        # 캘리브레이션 시야/품질 신뢰도 추출
        quality = float(calib.get("quality", 0.0))
        # 지정된 경로 비디오 파일 객체화
        cap = cv2.VideoCapture(str(path))
        # 원본 영상 FPS 세팅
        fps = clip.fps or 25.0
        # 분석 시작 프레임 인덱스 설정
        start = int(clip.start * fps)
        # 전체 프레임 수 가져오기
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        # 전체 프레임 수를 모른다면, 설정해둔 기본 최대 재생 시간으로 추정
        if total_frames <= 0:
            total_frames = start + int(MAX_SEC * fps)
        # 마지막으로 확인되어야 할 프레임 인덱스 지정(방어적 코드)
        end_frame = max(start + 1, total_frames)
        # 분석해야 될 전체 순수 프레임 스팬
        span = max(1, end_frame - start)
        # 스킵할 최소 기준 스텝(프레임 간격) 산출
        min_step = max(1, int(fps * STEP_SEC))
        # 실제 반복해서 점프할 균등 분할 샘플 슬라이드 간격 산출
        sample_step = max(min_step, int(span / MAX_SAMPLES) or 1)
        # 객체 감지용 로드된 YOLO 모델 인스턴스 소환
        model = _model()
        # 추적된 좌표 정보들을 담을 리스트
        points = []
        # 발견한 '공(Ball)' 객체 카운트 로그
        ball_count = 0
        # 발견한 '선수(Player)' 객체 카운트 로그
        player_count = 0
        # 실제로 추론을 수행한 샘플 프레임 누적 횟수
        samples = 0
        # 궤적이 끊기거나 너무 비정상적이라 버린 카운트 로그
        drop_count = 0
        # 프레임 반복을 위한 루프 인덱스 변수
        frame_idx = start
        # 칼만필터/스무딩 보정을 위한 직전 프레임 추적 기록 유지
        prev_point: Dict | None = None
        # X축 방향 이동 속도 추정치 변수
        vel_x = 0.0
        # Y축 방향 이동 속도 추정치 변수
        vel_y = 0.0
        # 스텝 당 이동하는 논리적인 시간 초 계산
        step_sec = max(sample_step / fps, 0.05)
        
        # 지정된 프레임 범위 전반에 걸쳐 순회
        while frame_idx < end_frame:
            # 캡처 객체의 포인터를 현재 프레임 인덱스로 이동
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            # 프레임 이미지 읽기 시도
            ok, frame = cap.read()
            # 프레임이 손상되었거나 없다면 스킵 후 계속 넘어가기
            if not ok:
                frame_idx += sample_step
                continue
            # 유효 샘플 프레임 카운트 추가
            samples += 1
            # YOLO 모델은 RGB를 선호하므로 BGR 원본 색공간 변환
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # 프레임 전체 면적에 대한 모델 추론 실행 (출력 메시지 무음화)
            res = model(rgb, verbose=False)[0]
            # 해당 프레임의 재생 위치 초(Timestamp) 확보
            ts = frame_idx / fps
            # 해당 프레임 내에서 발견된 관심 타겟 후보군 리스트
            cand = []
            
            # 모델이 내놓은 Bounding Box 결과를 순회
            for box in res.boxes:
                # 탐지 객체의 분류 ID 추출
                cls = int(box.cls[0])
                # 모델이 매긴 해당 객체의 신뢰도/정확성 확률 산출
                conf = float(box.conf[0])
                # 찾고있는 Ball 혹은 Player가 아니면 무시
                if cls not in (BALL_CLASS, PLAYER_CLASS):
                    continue
                # 신뢰도가 최저 설정치 이하인 쓰레기 객체는 무시
                if conf < MIN_CONF:
                    continue
                # 화면상의 픽셀 Bounding Box 4개 좌표(x1,y1,x2,y2) 획득
                xyxy = box.xyxy[0].cpu().numpy()
                # 상하좌우를 토대로 화상 객체의 X 중심축 위치 도출
                cx = float((xyxy[0] + xyxy[2]) / 2)
                # 상하좌우를 토대로 화상 객체의 Y(하단 발밑 치중) 위치 도출
                cy = float((xyxy[1] + xyxy[3]) / 2)
                
                # 정상적으로 화면 변환 매트릭스가 있는 상황이라면
                if mat is not None:
                    # 중심 픽셀 좌표를 2D 논리 마당 좌표(105x68)로 변환 투영
                    out = _pitch(np.array([cx, cy], dtype=np.float32), mat)
                    # 구장 바깥으로 튕겨나가지 않게 마당 규격 한도로 영역 보정
                    px = _clip(out[0], 0.0, 105.0)
                    py = _clip(out[1], 0.0, 68.0)
                    # 캘리브레이션 퀄리티에 따라 베이스 가중치 연산
                    base_conf = conf * max(0.25, quality)
                # 매트릭스가 없는 탑다운 영상이나 예외 상황
                else:
                    # 화면 절대 픽셀 길이를 마당 규격 스케일에 맞춰 비례 위치화
                    px = _norm(cx, frame.shape[1], 105.0)
                    py = _norm(cy, frame.shape[0], 68.0)
                    # 매트릭스 시야가 없어 신뢰도 0.22 고정 패널티 계수 적용
                    base_conf = conf * 0.22
                
                # 현재 처리중인 타깃의 속성을 문자열로 식별
                kind = "ball" if cls == BALL_CLASS else "player"
                # 발견 종류에 따라 통계치에 1씩 추가
                if kind == "ball":
                    ball_count += 1
                else:
                    player_count += 1
                
                # 플레이어보다는 주요 관심사인 작고 빠른 볼(Ball)에 어드밴티지 가중 부여
                class_bias = 1.0 if kind == "ball" else 0.65
                # 후보군 배열에 변환 좌표 및 신뢰도 조합 해시 추가
                cand.append({
                    "ts": ts,
                    "x": px,
                    "y": py,
                    "conf": base_conf * class_bias,
                    "kind": kind,
                })
            
            # 최종 채택된 베스트 좌표를 잠시 보관할 변수
            pick: Dict | None = None
            # 적어도 1개 이상의 객체가 프레임 안에 찍혔다면
            if cand:
                # 이전 프레임의 연계된 행적이 처음이거나 아예 없다면 최고 신뢰도 항목으로 지정
                if prev_point is None:
                    # 공을 좀 더 낫게 취급하며 가장 확률이 높은 항목 Pick
                    pick = max(cand, key=lambda row: row["conf"] + (0.12 if row["kind"] == "ball" else 0.0))
                # 이전 행적이 있어 추적 궤도를 예측할 수 있다면
                else:
                    # 속도를 등속 운동이라 가정하고 예상 도착 논리 좌표 도출
                    pred_x = float(prev_point["x"]) + vel_x * step_sec
                    pred_y = float(prev_point["y"]) + vel_y * step_sec
                    # 최고 적합도를 찾기 위한 임계값 변수
                    best_score = -1e9
                    
                    # 현재 프레임의 모든 후보들을 예측 지점과 비교
                    for row in cand:
                        # 후보 지점과 예측된 도착 지점간 물리적 x 거리
                        dx = float(row["x"]) - pred_x
                        # 후보 지점과 예측된 도착 지점간 물리적 y 거리
                        dy = float(row["y"]) - pred_y
                        # 유클리디안 물리 거리 차이(점프량) 산출
                        jump = math.hypot(dx, dy)
                        # 예상 궤도에서 너무 멀어지면 주는 운동량 감점 패널티 가중
                        motion_penalty = jump / 24.0
                        # 관심종목(Ball)에 추가 점수 부여
                        kind_bonus = 0.1 if row["kind"] == "ball" else 0.0
                        # 이전 프레임에서 점찍은 종류와 동일하다면 안정도 추가 점수 부여
                        stay_bonus = 0.05 if row["kind"] == prev_point.get("kind") else 0.0
                        # 위 요소들을 총 망라하여 객체 추적 채택 적합도 검수
                        score = float(row["conf"]) * 1.45 + kind_bonus + stay_bonus - motion_penalty
                        # 이전 베스트스코어보다 높다면 현재 항목을 Pick 갱신
                        if score > best_score:
                            best_score = score
                            pick = row
                            
                    # 예상된 항목이 터무니없는 물리 에러를 가졌는지 체크
                    if pick is not None:
                        # 이전 좌표 대비 실측 물리 이동 거리 산출
                        jump = math.hypot(float(pick["x"]) - float(prev_point["x"]), float(pick["y"]) - float(prev_point["y"]))
                        # 이동거리를 시간으로 나눠 초당 이동 제한 속도 검증
                        speed = jump / max(step_sec, 0.05)
                        # 속도가 45m/s가 넘는 물리 불가능 상태고, 확신율도 낮다면 그냥 버림
                        if speed > 45.0 and float(pick["conf"]) < 0.35:
                            drop_count += 1
                            pick = None
            
            # 최종적으로 유의미한 항목이 추출 채택되었다면 관성 운동량 제어 및 궤도 추가
            if pick is not None:
                # 이전 기록이 있어서 운동량 관성(Kalman-like) 통제가 필요하다면
                if prev_point is not None:
                    # 현재 채택 좌표와 과거 사이 실제 이동 변화 폭 델타
                    dx = float(pick["x"]) - float(prev_point["x"])
                    dy = float(pick["y"]) - float(prev_point["y"])
                    # 변화된 물리 이동 거리 길이
                    jump = math.hypot(dx, dy)
                    # 상당히 멀리 튀었고(14m), 모델 자체 확신율도 좀 낮을 경우엔 보수적 댐핑 처리
                    if jump > 14.0 and float(pick["conf"]) < 0.45:
                        # 신뢰도가 낮으므로 0.58 수준으로만 끌고와서 이동 제한
                        damp = 0.58
                        pick["x"] = float(prev_point["x"]) + dx * damp
                        pick["y"] = float(prev_point["y"]) + dy * damp
                        
                    # 최종 수정된 좌표를 기반으로 현재 단위 초당 프레임 이동 속도(vx, vy) 확보
                    cur_vx = (float(pick["x"]) - float(prev_point["x"])) / max(step_sec, 0.05)
                    cur_vy = (float(pick["y"]) - float(prev_point["y"])) / max(step_sec, 0.05)
                    # 기존 흐름 속도(0.42)와 현재 측정 속도(0.58) 블렌딩 추세 속도 지속
                    vel_x = vel_x * 0.42 + cur_vx * 0.58
                    vel_y = vel_y * 0.42 + cur_vy * 0.58
                # 트레일 리스트에 최종 확정 객체 스냅샷 좌표 추가
                points.append(pick)
                # 다음 번 순회를 위해 현재 포지션을 과거 기록으로 교체 탑재
                prev_point = pick
            # 루프 다 돌았으면 스킵 지정된 프레임 만큼만 인덱스 점프
            frame_idx += sample_step
        # 파일 핸들 자원 메모리 해제
        cap.release()
        # 모아진 포인트 궤적들에 대해 앞뒤 스무딩 평활화 보정 적용
        points = _smooth_points(points)
        # 궤적을 컨텍스트에 담고 노트 정보 종합 추가
        ctx["points"] = points
        ctx["notes"].append(f"points_{len(points)}")
        ctx["notes"].append(f"samples_{samples}")
        ctx["notes"].append(f"ball_{ball_count}")
        ctx["notes"].append(f"player_{player_count}")
        ctx["notes"].append(f"drops_{drop_count}")
        return ctx

# 4단계: 확보된 이동 궤적을 샅샅이 뒤져 돌파/터치를 분기하는 중요 이벤트 색인
class Event:
    # 파이프라인 버스 키 문자열 등록
    key = "event"

    def unit(self, ctx: Dict) -> Dict:
        # 트래킹 모듈에서 생성한 포인트 궤적 추출
        points = ctx.get("points", [])
        # 발견된 이동 궤적이 1개도 없으면 이벤트도 없음 반환
        if not points:
            ctx["events"] = []
            ctx["notes"].append("events_0")
            return ctx
        # 골문을 향하는 공격 방향 상의 중앙 타겟 좌표 등록 (105, 34)
        goal = (105.0, 34.0)
        # 시간순 모순이나 아웃오브오더 방지를 위한 타임스탬프 순차 정렬
        rows_src = sorted(points, key=lambda item: float(item["ts"]))
        # 계산 결과들이 부가적으로 덧붙여진 분석 리스트 배열
        rows = []
        # 이전 행적을 참조하기 위한 변수
        prev = None
        
        # 정렬된 모든 포인트 추적에 대해 속성 계산
        for item in rows_src:
            ts = float(item["ts"])
            x = float(item["x"])
            y = float(item["y"])
            # 중앙 골대 타겟까지의 절대 거리 계산
            dist = math.hypot(goal[0] - x, goal[1] - y)
            # 유효 슈팅 가능한 각도 사이즈 도출
            angle = _shot_angle(x, y)
            # 가장 첫 지점은 이전이 없으니 속도 0 할당
            if prev is None:
                vx = 0.0
                vy = 0.0
            # 이후 지점들은 구간 시간차를 이용해 단위 초당 이동 속도 성분 계산
            else:
                dt = max(0.05, ts - float(prev["ts"]))
                vx = (x - float(prev["x"])) / dt
                vy = (y - float(prev["y"])) / dt
                
            # 골문에 투사된 직진 진척 속도량 내적 산출
            to_goal_x = goal[0] - x
            to_goal_y = goal[1] - y
            goal_norm = max(1e-6, math.hypot(to_goal_x, to_goal_y))
            # 음수(후퇴)는 고려하지 않고 0.0으로 무시, 전진량만 추출
            toward_goal = max(0.0, (vx * to_goal_x + vy * to_goal_y) / goal_norm)
            
            # 거리가 가까울수록 점수가 높아지는 1.0 만점 거리 스코어
            dist_score = 1.0 / (1.0 + dist / 21.0)
            # 각도가 무각일수록 점수가 깎이는 각도 스코어
            angle_score = _clip((angle - 6.0) / 24.0, 0.0, 1.0)
            # 가파르게 전진하고 있을 수록 높은 진척 속도 스코어
            pace_score = _clip(toward_goal / 9.0, 0.0, 1.0)
            
            # 감지 종류 특수 처리 (공/선수)
            kind = item.get("kind", "ball")
            # 선수는 공보다 약간의 확률 저감 패널티 적용
            kind_scale = 1.0 if kind == "ball" else 0.76
            # 신뢰도 기반 스코어 조합 산출 (거리 비중 60%)
            score = float(item["conf"]) * (0.6 * dist_score + 0.25 * angle_score + 0.15 * pace_score) * kind_scale
            # 풍부해진 분석 정보를 배열로 다시 덮어씌움
            rows.append({
                "ts": ts,
                "x": x,
                "y": y,
                "conf": float(item["conf"]),
                "dist": dist,
                "angle": angle,
                "vx": vx,
                "vy": vy,
                "score": score,
                "kind": kind,
            })
            prev = item
            
        candidates = []
        # 구간 샘플이 넉넉하면 커트라인 0.025, 너무 빡빡하면 0.015로 조절
        peak_floor = 0.025 if len(rows) >= 20 else 0.015
        
        # 계산된 모든 행을 순회하며 국소 스코어 피크점(Local Maxima) 찾기
        for idx, row in enumerate(rows):
            # 주변 5프레임 반경 안쪽의 이웃 노드 지정
            left = max(0, idx - 2)
            right = min(len(rows), idx + 3)
            # 주변 구간 내 가장 스코어가 높았던 피크 스코어 도출
            local_max = max(item["score"] for item in rows[left:right])
            # 자신이 로컬 맹주 위치에 있으면서 절대 기준 컷선(Floor)을 넘는다면
            if row["score"] >= local_max * 0.9 and row["score"] >= peak_floor:
                # 유효 이벤트 후보군에 삽입
                candidates.append(row)
                
        # 만약 피크가 전혀 찾아지지 않았다면, 무조건 제일 높은 친구들 강제 소환 시작
        if not candidates:
            # 점수와 신뢰도가 높고 거리가 그나마 가까운 녀석들로 정렬 채용 준비
            backup = sorted(
                rows,
                key=lambda item: (item["score"], item["conf"], -item["dist"]),
                reverse=True,
            )
            for row in backup:
                # 너무 낮은 신뢰도와 72m 뒤쪽 후방의 무의미한 지점 방어 필터
                if float(row["conf"]) < 0.07 and float(row["dist"]) > 72.0:
                    continue
                # 조건에 들면 백업 캔디데이트로 구제
                candidates.append(row)
                # 최대 8개까지만 넣기
                if len(candidates) >= 8:
                    break
            # 대체 플로우를 탔다는 로그 기록 추가
            ctx["notes"].append("event_fallback")
            
        # 추출된 후보를 종합 점수순(유의미도)으로 정렬
        candidates.sort(key=lambda item: item["score"], reverse=True)
        picks = []
        # 너무 연달아 중복 생성되는 이벤트를 막기 위한 4초 쿨타임 지정
        min_gap = 4.0
        for row in candidates:
            # 기존 Pick에 들은 요소들과 시간 차이가 간격(Gap)보다 촘촘하면 버림
            if any(abs(row["ts"] - item["ts"]) < min_gap for item in picks):
                continue
            # 시간적 거리 한계를 만족했으니 Pick 리스트에 탑선
            picks.append(row)
            # 영상이 길어도 최대 5개의 핵심 키 모멘트만 뽑아내기
            if len(picks) >= 5:
                break
                
        # 다 돌았는데도 아무 피크도 못구했다면, 강제로 가장 스코어가 높았던 1개 무조건 추출
        if not picks and rows:
            picks.append(max(rows, key=lambda item: (item["score"], item["conf"])))
            ctx["notes"].append("event_single")
            
        # 이벤트는 시간 순서대로 뷰에 찍혀야 하므로 다시 정렬 세팅
        picks.sort(key=lambda item: item["ts"])
        # 최종 산출된 5개의 Key 이벤트 모멘트 컨텍스트에 싣기
        ctx["events"] = picks
        ctx["notes"].append(f"events_{len(picks)}")
        return ctx

# 5단계: 식별된 유효 이벤트(공격 찬스)가 얼마나 가치있는 득점 기회인지 평가
class Value:
    # 파이프라인 버스 식별 키워드
    key = "value"

    # 가치 평가 모듈의 메인 단위 함수
    def unit(self, ctx: Dict) -> Dict:
        # 이벤트 모듈이 산출해준 객체 배열 추출
        events = ctx.get("events", [])
        # 가치가 측정된 이벤트 객체들을 담아둘 배열
        rows = []
        for item in events:
            # 골대까지의 절대 물리 거리 추출
            dist = float(item["dist"])
            # 저장된 각도 값이 없으면 현재 위치를 기준으로 다시 생성 유도
            angle = float(item.get("angle", _shot_angle(float(item["x"]), float(item["y"]))))
            # 앞서 정의한 xG 기반 득점 기대 확률(가치) 산출 알고리즘 호출
            chance = _shot_value(dist, angle)
            # 영상 화질이나 인식률에 따른 신뢰도 감쇠(패널티) 적용
            trust = _clip(float(item.get("conf", 0.0)) / 0.75, 0.0, 1.0)
            # 원본 확률과 통계적 신뢰도를 7.5 : 2.5 비율로 혼합 적용하여 최종 가치 결정
            value = chance * (0.75 + 0.25 * trust)
            # 구해진 가치(Value) 필드를 추가하여 새로운 딕셔너리로 저장 (초기 변동량 delta는 0)
            rows.append({**item, "value": value, "delta": 0.0})
        # 측정 완료된 가치 리스트를 다시 컨텍스트에 덮어씌움
        ctx["values"] = rows
        # 평가된 이벤트 개수 로그 추가
        ctx["notes"].append(f"value_{len(rows)}")
        return ctx

# 6단계: 가치 평가가 완료된 이벤트에서 AI가 추천할 더 나은 대안 움직임을 탐색
class Suggest:
    # 파이프라인 버스 식별 키워드
    key = "suggest"

    # 타겟 제안 모듈의 메인 단위 함수
    def unit(self, ctx: Dict) -> Dict:
        # 가치 평가 리스트 확보
        values = ctx.get("values", [])
        # 원본 영상 클립 정보
        clip = ctx.get("clip")
        # 캘리브레이션 투영 매트릭스 확보
        calib = ctx.get("calib", {})
        # 역투영(논리->화면)을 위한 역행렬 확보
        inv = calib.get("inv")
        # 캘리브레이션 퀄리티 확보
        quality = float(calib.get("quality", 0.0))
        
        # 만약 이벤트 모멘텀이 1개도 채택되지 않은 빈깡통 영상이라면 (보완 로직)
        if not values:
            # 기본 프레임 분석 궤적들 로드
            points = ctx.get("points", [])
            if points:
                # 궤적들 중에서 그래도 슛 각이 열려있거나 신뢰도가 높은 대상을 씨앗(Seed)으로 억지 채용
                seed = max(
                    points,
                    key=lambda item: float(item.get("conf", 0.0)) + float(item.get("x", 0.0)) / 105.0 * 0.25,
                )
                x = float(seed["x"])
                y = float(seed["y"])
                # 타겟 대상의 현재 시점 유효 거리 측정
                dist = math.hypot(105.0 - x, 34.0 - y)
                # 시야 각도 추출
                angle = _shot_angle(x, y)
                # 가짜(Seed) 이벤트 요소 1개를 배열에 강제 생성
                values = [{
                    "ts": float(seed["ts"]),
                    "x": x,
                    "y": y,
                    "dist": dist,
                    "angle": angle,
                    "conf": float(seed.get("conf", 0.0)),
                    "vx": 0.0,
                    "vy": 0.0,
                    "value": _shot_value(dist, angle),
                }]
                ctx["notes"].append("suggest_seed")
                
        # 최종적으로 정리되어 반환될 AI 분석 모멘트 객체 리스트
        moments: List[Moment] = []
        # 모든 (보정된) 유효 찬스 이벤트들을 순회
        for item in values:
            # 현재 위치 좌표
            x = float(item["x"])
            y = float(item["y"])
            # 위치 기반 분석 수치들
            dist = float(item.get("dist", 0.0))
            angle = float(item.get("angle", _shot_angle(x, y)))
            # 이벤트 시점의 오리지널 득점 기회 가치 (베이스)
            base_value = float(item.get("value", _shot_value(dist, angle)))
            # 당시 선수의 이동 관성 벡터
            vx = float(item.get("vx", 0.0))
            vy = float(item.get("vy", 0.0))
            # 당장의 스피드 도출
            speed = math.hypot(vx, vy)
            
            # 사실상 정지 상태라면 골대 방향 직선을 전진 축으로 임의 설정
            if speed < 0.2:
                hx, hy = 1.0, (34.0 - y) * 0.03
            # 뛰는 중이라면 진행 방향(이동 벡터)을 헤딩 방향 리더 축으로 지정
            else:
                hx = vx / speed
                hy = vy / speed
                
            # 진행 방향에 완전히 치우치지 않고 골대 방향 공격 성향을 약간 섞음 (가중 합성)
            hx = hx * 0.45 + 0.55
            # 벡터 정규화(길이 1) 처리
            norm = max(1e-6, math.hypot(hx, hy))
            hx /= norm
            hy /= norm
            # 전진 축에 대한 직교(수직) 벡터 산출 (좌우 이동성 파악용)
            px = -hy
            py = hx
            
            # 현재 횡축 포지션의 깊이에 비례한 추가 전진 한계 베이스 탐색 길이
            forward_base = 5.0 if x >= 88.0 else 8.0 if x >= 78.0 else 11.0 if x >= 68.0 else 14.0
            # 골대 중앙(34)으로 수렴하고자 하는 마그네틱 인력
            center_pull = (34.0 - y) * 0.22
            
            # 최고 상황 가상 시뮬레이션의 디폴트는 현재 제자리
            best = {
                "x": x,
                "y": y,
                "value": base_value,
                "objective": base_value,
            }
            
            # 여러 전진 거리 후보(앞, 중간, 약간 앞) 순회
            for forward in [max(2.0, forward_base - 4.0), max(3.0, forward_base - 1.0), forward_base + 2.0]:
                # 여러 좌우 횡단 거리 후보 순회
                for lateral in [-6.0, -3.0, 0.0, 3.0, 6.0]:
                    # 가상 목표 시점의 x 좌표 도출 및 구장 한계 클램핑 적용
                    sx = _clip(x + hx * forward + px * lateral, 0.0, 104.0)
                    # 가상 목표 시점의 y 좌표 도출 (중앙 자석 중력 포함)
                    sy = _clip(y + hy * forward + py * lateral + center_pull * 0.35, 0.0, 68.0)
                    
                    # 이동했을 때 가정되는 거리와 각도
                    s_dist = math.hypot(105.0 - sx, 34.0 - sy)
                    s_angle = _shot_angle(sx, sy)
                    # 시뮬레이션 한 도착 지점의 생존 가능 가치 (Expected Value)
                    s_value = _shot_value(s_dist, s_angle)
                    # 실제로 도달하기 위해 소모해야 하는 물리적 이동 비용 (체력/시간)
                    move_cost = math.hypot(sx - x, sy - y)
                    # 중앙(Zone 14 주변)에 가까우면 가산되는 전략적 전술 가치 보너스
                    central_bonus = 0.04 * (1.0 - min(1.0, abs(sy - 34.0) / 34.0))
                    # 시뮬 예상 가치 + 센터 보너스 - 이동 비용 감가로 최종 "목적성" 점수 부여
                    objective = s_value + central_bonus - move_cost * 0.005
                    
                    # 지금껏 탐색한 목적 중 최고로 유능하다면 베스트 교체
                    if objective > float(best["objective"]):
                        best = {
                            "x": sx,
                            "y": sy,
                            "value": s_value,
                            "objective": objective,
                        }
                        
            # 탐색이 끝난 최적 추천 이동 루트 좌표
            sx = float(best["x"])
            sy = float(best["y"])
            # 최고 최적해에서의 가치 기댓값
            best_value = float(best["value"])
            # 제자리 가치 대비 향상된 기댓값의 비율 델타폭을 스케일링
            gain = (best_value - base_value) * 28.0
            # 소숫점 첫째 자리까지만 예쁘게 끊어서 로깅
            gain = round(gain, 1)
            
            # 정보 전달을 위한 상황 문자열 렌더링
            lane = _lane(x)
            zone = _zone(y)
            speed = math.hypot(vx, vy)
            label = _moment_label(x, y, dist, angle, vx, vy)
            tempo_note = _tempo_note(x, y, vx, vy)
            # 프론트 카드 UI에서 보여줄 긴 상세 노트 문자 포매팅
            note = (
                f"{lane} · {zone} · 거리 {dist:.1f}m · 각도 {angle:.0f}° · "
                f"속도 {speed:.1f}m/s · {tempo_note} · 신뢰도 {float(item.get('conf', 0.0)) * 100:.0f}%"
            )
            # 영상 렌더링을 위한 픽셀 좌표 역투영 컨테이너
            overlay = None
            if clip is not None:
                # 지금 내 마당 좌표를 픽셀로 변환
                ax, ay = _pitch_px((x, y), inv, clip)
                # 추천할 마당 좌표를 픽셀로 변환
                sx2, sy2 = _pitch_px((sx, sy), inv, clip)
                # 골대 타겟 좌표를 픽셀로 변환
                gx, gy = _pitch_px((105.0, 34.0), inv, clip)
                # 프론트 화살표 렌더링을 돕기 위해 픽셀 객체 탑재
                overlay = Overlay(
                    actual_px={"x": ax, "y": ay},
                    suggest_px={"x": sx2, "y": sy2},
                    goal_px={"x": gx, "y": gy},
                    angle=angle,
                    quality=quality,
                )
            # 최종 완성된 1건의 Moment 객체 조립 후 저장
            moments.append(
                Moment(
                    ts=float(item["ts"]),
                    label=label,
                    actual={"x": x, "y": y},
                    suggest={"x": sx, "y": sy},
                    delta=gain,
                    note=note,
                    conf=float(item["conf"]),
                    overlay=overlay,
                )
            )
        # 생성된 모멘텀 배열을 컨텍스트에 담고 상태 변경
        ctx["moments"] = moments
        ctx["notes"].append(f"suggest_{len(moments)}")
        # 프로세스 깊이가 refined 레벨까지 파고들었음을 기록
        ctx["mode"] = "refined"
        return ctx

# 7단계: 전체 이동과 추천 이벤트를 결합해 경기장 과열 분포 렌더링
class Heat:
    # 파이프라인 버스 식별 키
    key = "heat"

    def unit(self, ctx: Dict) -> Dict:
        # 일반 객체 추적 행적 전체 경로
        points = ctx.get("points", [])
        # 추천된 파이널 이벤트 모멘텀 분석본
        moments = ctx.get("moments", [])
        # 원본 영상 해상도 정보
        clip = ctx.get("clip")
        calib = ctx.get("calib", {})
        # 매트릭스 역행렬
        inv = calib.get("inv")
        # 행적이나 변환 인자가 부족하면 생성 스킵
        if not points or clip is None:
            return ctx
            
        # 히트맵 상수를 적용해 가로/세로 매트릭스 그리드 사이즈 할당
        rows = HEAT_ROWS
        cols = HEAT_COLS
        # 실제 움직임이 투영될 그리드 초기화 (0 세팅 2차원 공간)
        grid = [[0.0 for _ in range(cols)] for _ in range(rows)]
        # 전체 행적을 순회하면서 머무른 곳에 체류 가중치 ++
        for item in points:
            # 자신의 x,y 좌표 배열 공간 인덱스 매핑
            row, col = _grid_idx(float(item["x"]), float(item["y"]), rows, cols)
            # 확신(Conf) 수준만큼 해당 칸에 열기 붓기
            grid[row][col] += float(item.get("conf", 0.0))
            
        # AI가 추천한 추천 이동 지점들이 집중 투영될 예상 목표 그리드
        suggest_grid = [[0.0 for _ in range(cols)] for _ in range(rows)]
        for moment in moments:
            row, col = _grid_idx(float(moment.suggest["x"]), float(moment.suggest["y"]), rows, cols)
            # 확신도에 비례해 최소 0.2 이상으로 추천 열점 붓기
            suggest_grid[row][col] += max(0.2, float(moment.conf))
            
        # 프론트 렌더링 시 투명도 정규화를 목적으로 가장 높은(뜨거운) 피크값 추출
        max_val = max([max(row) for row in grid] + [max(row) for row in suggest_grid] + [0.0])
        # 일반 누적 열기를 픽셀 단위 4각형 HeatCell 배열로 치환
        cells = _heat_cells(grid, inv, clip)
        # 추천 누적 열기를 픽셀 배열로 치환
        suggest_cells = _heat_cells(suggest_grid, inv, clip)
        
        # Heatmap 컨테이너 객체 생성 및 컨텍스트에 싣고 완료 표기
        ctx["heatmap"] = Heatmap(
            rows=rows,
            cols=cols,
            cells=cells,
            suggest_cells=suggest_cells,
            max=max_val,
        )
        ctx["notes"].append("heatmap_ok")
        return ctx

# 최상단 실행 주체: 여러 파이프라인 단위를 연속 실행하는 워크플로우 팩토리 객체
class Pipe:
    # 파이프 인스턴스 초기화 시 수행 단계들을 주입받음
    def __init__(self, steps: List[Any] | None = None) -> None:
        # 전달받은게 없으면 기본 1~7단계 프로세스 순서대로 풀 세팅
        self.steps = steps or [Link(), Calib(), Track(), Event(), Value(), Suggest(), Heat()]

    # 영상 분석 작업 요청이 들어왔을 때 호출되는 스레드 진입 함수
    def flow(self, job_id: str, url: str, file_path: str | None = None) -> Report:
        # 단계별로 돌려가며 주고받을 최상단 컨텍스트 데이터 스토어 선언
        ctx: Dict = {
            "job_id": job_id,
            "url": url,
            "notes": [],
            "mode": "basic",
            "file_path": file_path,
        }
        # 지정된 파이프 흐름 배열을 돌면서 이전 산출물 컨텍스트를 다음 타겟에 먹임 (Chain)
        for step in self.steps:
            ctx = step.unit(ctx)
            
        # 최종적으로 컨텍스트에서 모멘트 모음 회수
        moments = ctx.get("moments", [])
        # 성공적으로 만들어졌으면 ok, 비었으면 empty 상태 할당
        status = "empty" if not moments else "ok"
        
        # 프론트에 반환할 최종 완성 Report 스펙 객체 렌더링
        report = Report(
            job_id=job_id,
            status=status,
            clip=ctx["clip"],
            moments=moments,
            notes=ctx["notes"],
            mode=ctx.get("mode", "basic"),
            heatmap=ctx.get("heatmap"),
        )
        return report

def payload(report: Report) -> Dict:
    data = asdict(report)
    data["clip"] = asdict(report.clip)
    data["moments"] = [asdict(item) for item in report.moments]
    if report.heatmap is not None:
        data["heatmap"] = asdict(report.heatmap)
    return data
