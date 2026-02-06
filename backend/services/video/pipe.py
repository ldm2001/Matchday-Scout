import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Tuple, TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import math
import inspect
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from yt_dlp import YoutubeDL
except ImportError:
    YoutubeDL = None

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

if TYPE_CHECKING:
    from ultralytics import YOLO as YOLOType

try:
    import torch
except ImportError:
    torch = None

from .model import Clip, HeatCell, Heatmap, Moment, Overlay, Report

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "cache" / "video"
CACHE.mkdir(parents=True, exist_ok=True)

MAX_SEC = 90
STEP_SEC = 0.5
MAX_SAMPLES = 180
MIN_CONF = 0.15
MODEL = None
HEAT_ROWS = 12
HEAT_COLS = 16
BALL_CLASS = 32
PLAYER_CLASS = 0

# torch 안전 로드 허용
def _torch_safe() -> None:
    if torch is None:
        return
    serial = getattr(torch, "serialization", None)
    if serial is None:
        return
    add = getattr(serial, "add_safe_globals", None)
    if add is None:
        return
    try:
        from ultralytics.nn.tasks import DetectionModel
        import torch.nn as nn
    except Exception:
        return
    extra = []
    extra_nn = []
    try:
        import ultralytics.nn.modules as u
        extra = [obj for _, obj in vars(u).items() if inspect.isclass(obj)]
    except Exception:
        extra = []
    try:
        extra_nn = [obj for _, obj in vars(nn).items() if inspect.isclass(obj)]
    except Exception:
        extra_nn = []
    try:
        add([DetectionModel, *extra, *extra_nn])
    except Exception:
        return


def _profile_hint(browser: str) -> str | None:
    if sys.platform != "darwin":
        return None
    base = None
    if browser == "chrome":
        base = Path.home() / "Library/Application Support/Google/Chrome"
    elif browser == "edge":
        base = Path.home() / "Library/Application Support/Microsoft Edge"
    elif browser == "brave":
        base = Path.home() / "Library/Application Support/BraveSoftware/Brave-Browser"
    if not base or not base.exists():
        return None
    picks = []
    names = ["Default"]
    names.extend([p.name for p in base.glob("Profile *")])
    for name in names:
        cookie = base / name / "Cookies"
        if cookie.exists():
            picks.append((name, cookie.stat().st_mtime))
    if not picks:
        return None
    picks.sort(key=lambda x: x[1], reverse=True)
    return picks[0][0]

def _sec(val: str) -> int:
    if not val:
        return 0
    raw = val.strip()
    if raw.isdigit():
        return int(raw)
    total = 0
    buf = ""
    for ch in raw:
        if ch.isdigit():
            buf += ch
            continue
        if not buf:
            continue
        num = int(buf)
        if ch == "h":
            total += num * 3600
        elif ch == "m":
            total += num * 60
        elif ch == "s":
            total += num
        buf = ""
    if buf:
        total += int(buf)
    return total

# 유튜브 id 추출
def _vid_id(url: str) -> Tuple[str, int]:
    if not url:
        return "", 0
    info = urlparse(url)
    host = info.netloc.lower()
    path = info.path.strip("/")
    qs = parse_qs(info.query)
    vid = ""
    if "youtu.be" in host:
        vid = path.split("/")[0]
    elif "youtube.com" in host:
        if path.startswith("watch"):
            vid = qs.get("v", [""])[0]
        elif path.startswith("shorts/"):
            vid = path.split("/")[1] if "/" in path else ""
        elif path.startswith("embed/"):
            vid = path.split("/")[1] if "/" in path else ""
    start = _sec(qs.get("t", qs.get("start", ["0"]))[0])
    return vid, start

# 파일 클립 메타
def _clip_path(path: Path) -> Clip:
    if cv2 is None:
        raise RuntimeError("opencv missing")
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    cap.release()
    name = path.stem
    return Clip(url=str(path), video_id=name, start=0, fps=fps, width=width, height=height)

# YOLO 모델 로드
def _model() -> "YOLOType":
    global MODEL
    if MODEL is None:
        if YOLO is None:
            raise RuntimeError("ultralytics missing")
        _torch_safe()
        MODEL = YOLO("yolov8n.pt")
    return MODEL

# 잔디 마스크
def _mask(frame: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower = np.array([35, 35, 35])
    upper = np.array([85, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask

def _box(pts: np.ndarray) -> np.ndarray:
    total = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).reshape(-1)
    tl = pts[np.argmin(total)]
    br = pts[np.argmax(total)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype=np.float32)

# 필드 좌표 변환
def _pitch(pt: np.ndarray, mat: np.ndarray) -> np.ndarray:
    pack = np.array([[pt]], dtype=np.float32)
    out = cv2.perspectiveTransform(pack, mat)
    return out[0][0]

def _clip(val: float, low: float, high: float) -> float:
    return float(max(low, min(high, val)))

def _norm(val: float, size: float, scale: float) -> float:
    if size <= 0:
        return 0.0
    return _clip(val / size * scale, 0.0, scale)

def _pitch_px(pt: Tuple[float, float], inv: np.ndarray | None, clip: Clip) -> Tuple[float, float]:
    if cv2 is not None and inv is not None:
        pack = np.array([[pt]], dtype=np.float32)
        out = cv2.perspectiveTransform(pack, inv)
        return float(out[0][0][0]), float(out[0][0][1])
    width = clip.width or 0
    height = clip.height or 0
    if width <= 0 or height <= 0:
        return 0.0, 0.0
    return float(pt[0] / 105.0 * width), float(pt[1] / 68.0 * height)

def _grid_idx(x: float, y: float, rows: int, cols: int) -> Tuple[int, int]:
    col = int(_clip(x / 105.0 * cols, 0, cols - 1))
    row = int(_clip(y / 68.0 * rows, 0, rows - 1))
    return row, col

def _heat_cells(grid: List[List[float]], inv: np.ndarray | None, clip: Clip) -> List[HeatCell]:
    cells: List[HeatCell] = []
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    for row in range(rows):
        for col in range(cols):
            x0 = col / cols * 105.0
            x1 = (col + 1) / cols * 105.0
            y0 = row / rows * 68.0
            y1 = (row + 1) / rows * 68.0
            p1 = _pitch_px((x0, y0), inv, clip)
            p2 = _pitch_px((x1, y0), inv, clip)
            p3 = _pitch_px((x1, y1), inv, clip)
            p4 = _pitch_px((x0, y1), inv, clip)
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
    return cells

def _shot_angle(x: float, y: float) -> float:
    left = (105.0, 34.0 - 3.66)
    right = (105.0, 34.0 + 3.66)
    v1 = (left[0] - x, left[1] - y)
    v2 = (right[0] - x, right[1] - y)
    denom = math.hypot(*v1) * math.hypot(*v2)
    if denom <= 0:
        return 0.0
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    cosv = max(-1.0, min(1.0, dot / denom))
    return math.degrees(math.acos(cosv))

def _lane(x: float) -> str:
    if x >= 88.0:
        return "박스 안"
    if x >= 80.0:
        return "박스 근처"
    return "중앙 지역"

def _zone(y: float) -> str:
    if y < 22.5:
        return "좌측"
    if y > 45.5:
        return "우측"
    return "중앙"


def _shot_value(dist: float, angle: float) -> float:
    dist_term = 1.0 / (1.0 + math.exp((dist - 18.0) / 5.5))
    angle_term = 1.0 / (1.0 + math.exp(-(angle - 14.0) / 5.0))
    raw = 0.05 + 0.75 * dist_term + 0.2 * angle_term
    return _clip(raw, 0.0, 0.98)


def _moment_label(
    x: float,
    y: float,
    dist: float,
    angle: float,
    vx: float,
    vy: float,
) -> str:
    speed = math.hypot(vx, vy)
    to_goal_x = 105.0 - x
    to_goal_y = 34.0 - y
    goal_norm = max(1e-6, math.hypot(to_goal_x, to_goal_y))
    toward_goal = (vx * to_goal_x + vy * to_goal_y) / goal_norm
    center_gap = abs(y - 34.0)
    lateral_speed = abs(vy)

    if dist <= 13.5 and angle >= 15.0:
        return "골문 정면 결정 찬스"
    if x >= 96.0 and center_gap >= 10.0:
        return "바이라인 침투"
    if x >= 90.0 and center_gap <= 9.0 and toward_goal >= 2.0:
        return "컷백 유도 침투"
    if x >= 84.0 and center_gap >= 11.0:
        return "하프스페이스 파고듦"
    if dist <= 28.0 and angle < 10.0:
        return "박스 외곽 슈팅 준비"
    if speed >= 5.0 and toward_goal >= 2.5:
        return "전환 속공 전개"
    if lateral_speed >= max(2.2, speed * 0.58) and x >= 60.0:
        return "측면 스위치 전개"
    if x < 62.0 and toward_goal >= 2.0 and speed >= 3.5:
        return "압박 회피 전진"
    if speed < 1.2 and x < 70.0:
        return "점유 안정 빌드업"
    if x >= 88.0:
        return "박스 진입"
    if x >= 74.0:
        return "공격 전개"
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


def _smooth_points(points: List[Dict], window: int = 2) -> List[Dict]:
    if len(points) < 3:
        return points
    smooth: List[Dict] = []
    size = len(points)
    for idx, item in enumerate(points):
        x_acc = 0.0
        y_acc = 0.0
        w_acc = 0.0
        left = max(0, idx - window)
        right = min(size, idx + window + 1)
        for pos in range(left, right):
            peer = points[pos]
            hop = abs(pos - idx)
            dist_w = 1.0 / (1.0 + hop)
            conf_w = max(0.05, float(peer.get("conf", 0.1)))
            w = dist_w * conf_w
            x_acc += float(peer["x"]) * w
            y_acc += float(peer["y"]) * w
            w_acc += w
        if w_acc <= 0:
            smooth.append(item.copy())
            continue
        target_x = x_acc / w_acc
        target_y = y_acc / w_acc
        blend = 0.62 if 0 < idx < size - 1 else 0.28
        smooth.append({
            **item,
            "x": float(item["x"]) * (1.0 - blend) + target_x * blend,
            "y": float(item["y"]) * (1.0 - blend) + target_y * blend,
        })
    for idx in range(1, len(smooth)):
        prev = smooth[idx - 1]
        cur = smooth[idx]
        dt = max(0.2, float(cur["ts"]) - float(prev["ts"]))
        max_step = 18.0 * dt + 0.8
        dx = float(cur["x"]) - float(prev["x"])
        dy = float(cur["y"]) - float(prev["y"])
        dist = math.hypot(dx, dy)
        if dist > max_step and dist > 0:
            ratio = max_step / dist
            cur["x"] = float(prev["x"]) + dx * ratio
            cur["y"] = float(prev["y"]) + dy * ratio
    return smooth

class Link:
    key = "link"

    def unit(self, ctx: Dict) -> Dict:
        if YoutubeDL is None:
            raise RuntimeError("yt_dlp missing")
        if ctx.get("file_path"):
            path = Path(ctx["file_path"]).expanduser().resolve()
            if not path.exists():
                raise RuntimeError("file missing")
            ctx["path"] = path
            ctx["clip"] = _clip_path(path)
            ctx["notes"].append("file_ok")
            return ctx
        url = ctx["url"]
        vid, start = _vid_id(url)
        if not vid:
            ctx["notes"].append("video_id_missing")
        out = str(CACHE / "%(id)s.%(ext)s")
        opts = {
            "outtmpl": out,
            "format": "mp4/best",
            "quiet": True,
            "noplaylist": True,
        }
        cookie_file = os.getenv("VIDEO_COOKIE_FILE")
        if cookie_file:
            opts["cookiefile"] = cookie_file
            ctx["notes"].append("cookie_file")
        browser = os.getenv("VIDEO_COOKIE_BROWSER")
        profile = os.getenv("VIDEO_COOKIE_PROFILE")
        if not browser and sys.platform == "darwin":
            browser = "chrome"
        if browser and not profile:
            profile = _profile_hint(browser)
        if browser:
            opts["cookiesfrombrowser"] = (browser, profile) if profile else (browser,)
            ctx["notes"].append(f"cookie_{browser}")
            if profile:
                ctx["notes"].append(f"profile_{profile}")
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(info))
        if cv2 is None:
            raise RuntimeError("opencv missing")
        cap = cv2.VideoCapture(str(path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        cap.release()
        ctx["path"] = path
        ctx["clip"] = Clip(url=url, video_id=vid, start=start, fps=fps, width=width, height=height)
        ctx["notes"].append("link_ok")
        return ctx

class Calib:
    key = "calib"

    def unit(self, ctx: Dict) -> Dict:
        if cv2 is None:
            raise RuntimeError("opencv missing")
        path = ctx["path"]
        start = ctx["clip"].start
        cap = cv2.VideoCapture(str(path))
        cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            ctx["calib"] = {"mat": None, "quality": 0.0}
            ctx["notes"].append("calib_skip")
            return ctx
        mask = _mask(frame)
        area = float(mask.sum()) / 255.0
        total = frame.shape[0] * frame.shape[1]
        ratio = area / total if total else 0.0
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            ctx["calib"] = {"mat": None, "quality": 0.0}
            ctx["notes"].append("calib_none")
            return ctx
        top = max(cnts, key=cv2.contourArea)
        rect = cv2.minAreaRect(top)
        box = cv2.boxPoints(rect)
        src = _box(np.array(box, dtype=np.float32))
        dst = np.array([[0, 0], [105, 0], [105, 68], [0, 68]], dtype=np.float32)
        mat = cv2.getPerspectiveTransform(src, dst)
        inv = cv2.getPerspectiveTransform(dst, src)
        quality = _clip(ratio * 1.6, 0.0, 1.0)
        ctx["calib"] = {"mat": mat, "inv": inv, "quality": quality}
        ctx["notes"].append(f"calib_{quality:.2f}")
        return ctx

class Track:
    key = "track"

    def unit(self, ctx: Dict) -> Dict:
        if cv2 is None:
            raise RuntimeError("opencv missing")
        path = ctx["path"]
        clip = ctx["clip"]
        calib = ctx.get("calib", {})
        mat = calib.get("mat")
        quality = float(calib.get("quality", 0.0))
        cap = cv2.VideoCapture(str(path))
        fps = clip.fps or 25.0
        start = int(clip.start * fps)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total_frames <= 0:
            total_frames = start + int(MAX_SEC * fps)
        end_frame = max(start + 1, total_frames)
        span = max(1, end_frame - start)
        min_step = max(1, int(fps * STEP_SEC))
        sample_step = max(min_step, int(span / MAX_SAMPLES) or 1)
        model = _model()
        points = []
        ball_count = 0
        player_count = 0
        samples = 0
        drop_count = 0
        frame_idx = start
        prev_point: Dict | None = None
        vel_x = 0.0
        vel_y = 0.0
        step_sec = max(sample_step / fps, 0.05)
        while frame_idx < end_frame:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ok, frame = cap.read()
            if not ok:
                frame_idx += sample_step
                continue
            samples += 1
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = model(rgb, verbose=False)[0]
            ts = frame_idx / fps
            cand = []
            for box in res.boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                if cls not in (BALL_CLASS, PLAYER_CLASS):
                    continue
                if conf < MIN_CONF:
                    continue
                xyxy = box.xyxy[0].cpu().numpy()
                cx = float((xyxy[0] + xyxy[2]) / 2)
                cy = float((xyxy[1] + xyxy[3]) / 2)
                if mat is not None:
                    out = _pitch(np.array([cx, cy], dtype=np.float32), mat)
                    px = _clip(out[0], 0.0, 105.0)
                    py = _clip(out[1], 0.0, 68.0)
                    base_conf = conf * max(0.25, quality)
                else:
                    px = _norm(cx, frame.shape[1], 105.0)
                    py = _norm(cy, frame.shape[0], 68.0)
                    base_conf = conf * 0.22
                kind = "ball" if cls == BALL_CLASS else "player"
                if kind == "ball":
                    ball_count += 1
                else:
                    player_count += 1
                class_bias = 1.0 if kind == "ball" else 0.65
                cand.append({
                    "ts": ts,
                    "x": px,
                    "y": py,
                    "conf": base_conf * class_bias,
                    "kind": kind,
                })
            pick: Dict | None = None
            if cand:
                if prev_point is None:
                    pick = max(cand, key=lambda row: row["conf"] + (0.12 if row["kind"] == "ball" else 0.0))
                else:
                    pred_x = float(prev_point["x"]) + vel_x * step_sec
                    pred_y = float(prev_point["y"]) + vel_y * step_sec
                    best_score = -1e9
                    for row in cand:
                        dx = float(row["x"]) - pred_x
                        dy = float(row["y"]) - pred_y
                        jump = math.hypot(dx, dy)
                        motion_penalty = jump / 24.0
                        kind_bonus = 0.1 if row["kind"] == "ball" else 0.0
                        stay_bonus = 0.05 if row["kind"] == prev_point.get("kind") else 0.0
                        score = float(row["conf"]) * 1.45 + kind_bonus + stay_bonus - motion_penalty
                        if score > best_score:
                            best_score = score
                            pick = row
                    if pick is not None:
                        jump = math.hypot(float(pick["x"]) - float(prev_point["x"]), float(pick["y"]) - float(prev_point["y"]))
                        speed = jump / max(step_sec, 0.05)
                        if speed > 45.0 and float(pick["conf"]) < 0.35:
                            drop_count += 1
                            pick = None
            if pick is not None:
                if prev_point is not None:
                    dx = float(pick["x"]) - float(prev_point["x"])
                    dy = float(pick["y"]) - float(prev_point["y"])
                    jump = math.hypot(dx, dy)
                    if jump > 14.0 and float(pick["conf"]) < 0.45:
                        damp = 0.58
                        pick["x"] = float(prev_point["x"]) + dx * damp
                        pick["y"] = float(prev_point["y"]) + dy * damp
                    cur_vx = (float(pick["x"]) - float(prev_point["x"])) / max(step_sec, 0.05)
                    cur_vy = (float(pick["y"]) - float(prev_point["y"])) / max(step_sec, 0.05)
                    vel_x = vel_x * 0.42 + cur_vx * 0.58
                    vel_y = vel_y * 0.42 + cur_vy * 0.58
                points.append(pick)
                prev_point = pick
            frame_idx += sample_step
        cap.release()
        points = _smooth_points(points)
        ctx["points"] = points
        ctx["notes"].append(f"points_{len(points)}")
        ctx["notes"].append(f"samples_{samples}")
        ctx["notes"].append(f"ball_{ball_count}")
        ctx["notes"].append(f"player_{player_count}")
        ctx["notes"].append(f"drops_{drop_count}")
        return ctx

class Event:
    key = "event"

    def unit(self, ctx: Dict) -> Dict:
        points = ctx.get("points", [])
        if not points:
            ctx["events"] = []
            ctx["notes"].append("events_0")
            return ctx
        goal = (105.0, 34.0)
        rows_src = sorted(points, key=lambda item: float(item["ts"]))
        rows = []
        prev = None
        for item in rows_src:
            ts = float(item["ts"])
            x = float(item["x"])
            y = float(item["y"])
            dist = math.hypot(goal[0] - x, goal[1] - y)
            angle = _shot_angle(x, y)
            if prev is None:
                vx = 0.0
                vy = 0.0
            else:
                dt = max(0.05, ts - float(prev["ts"]))
                vx = (x - float(prev["x"])) / dt
                vy = (y - float(prev["y"])) / dt
            to_goal_x = goal[0] - x
            to_goal_y = goal[1] - y
            goal_norm = max(1e-6, math.hypot(to_goal_x, to_goal_y))
            toward_goal = max(0.0, (vx * to_goal_x + vy * to_goal_y) / goal_norm)
            dist_score = 1.0 / (1.0 + dist / 21.0)
            angle_score = _clip((angle - 6.0) / 24.0, 0.0, 1.0)
            pace_score = _clip(toward_goal / 9.0, 0.0, 1.0)
            kind = item.get("kind", "ball")
            kind_scale = 1.0 if kind == "ball" else 0.76
            score = float(item["conf"]) * (0.6 * dist_score + 0.25 * angle_score + 0.15 * pace_score) * kind_scale
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
        peak_floor = 0.025 if len(rows) >= 20 else 0.015
        for idx, row in enumerate(rows):
            left = max(0, idx - 2)
            right = min(len(rows), idx + 3)
            local_max = max(item["score"] for item in rows[left:right])
            if row["score"] >= local_max * 0.9 and row["score"] >= peak_floor:
                candidates.append(row)
        if not candidates:
            backup = sorted(
                rows,
                key=lambda item: (item["score"], item["conf"], -item["dist"]),
                reverse=True,
            )
            for row in backup:
                if float(row["conf"]) < 0.07 and float(row["dist"]) > 72.0:
                    continue
                candidates.append(row)
                if len(candidates) >= 8:
                    break
            ctx["notes"].append("event_fallback")
        candidates.sort(key=lambda item: item["score"], reverse=True)
        picks = []
        min_gap = 4.0
        for row in candidates:
            if any(abs(row["ts"] - item["ts"]) < min_gap for item in picks):
                continue
            picks.append(row)
            if len(picks) >= 5:
                break
        if not picks and rows:
            picks.append(max(rows, key=lambda item: (item["score"], item["conf"])))
            ctx["notes"].append("event_single")
        picks.sort(key=lambda item: item["ts"])
        ctx["events"] = picks
        ctx["notes"].append(f"events_{len(picks)}")
        return ctx

class Value:
    key = "value"

    def unit(self, ctx: Dict) -> Dict:
        events = ctx.get("events", [])
        rows = []
        for item in events:
            dist = float(item["dist"])
            angle = float(item.get("angle", _shot_angle(float(item["x"]), float(item["y"]))))
            chance = _shot_value(dist, angle)
            trust = _clip(float(item.get("conf", 0.0)) / 0.75, 0.0, 1.0)
            value = chance * (0.75 + 0.25 * trust)
            rows.append({**item, "value": value, "delta": 0.0})
        ctx["values"] = rows
        ctx["notes"].append(f"value_{len(rows)}")
        return ctx


class Suggest:
    key = "suggest"

    def unit(self, ctx: Dict) -> Dict:
        values = ctx.get("values", [])
        clip = ctx.get("clip")
        calib = ctx.get("calib", {})
        inv = calib.get("inv")
        quality = float(calib.get("quality", 0.0))
        if not values:
            points = ctx.get("points", [])
            if points:
                seed = max(
                    points,
                    key=lambda item: float(item.get("conf", 0.0)) + float(item.get("x", 0.0)) / 105.0 * 0.25,
                )
                x = float(seed["x"])
                y = float(seed["y"])
                dist = math.hypot(105.0 - x, 34.0 - y)
                angle = _shot_angle(x, y)
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
        moments: List[Moment] = []
        for item in values:
            x = float(item["x"])
            y = float(item["y"])
            dist = float(item.get("dist", 0.0))
            angle = float(item.get("angle", _shot_angle(x, y)))
            base_value = float(item.get("value", _shot_value(dist, angle)))
            vx = float(item.get("vx", 0.0))
            vy = float(item.get("vy", 0.0))
            speed = math.hypot(vx, vy)
            if speed < 0.2:
                hx, hy = 1.0, (34.0 - y) * 0.03
            else:
                hx = vx / speed
                hy = vy / speed
            hx = hx * 0.45 + 0.55
            norm = max(1e-6, math.hypot(hx, hy))
            hx /= norm
            hy /= norm
            px = -hy
            py = hx
            forward_base = 5.0 if x >= 88.0 else 8.0 if x >= 78.0 else 11.0 if x >= 68.0 else 14.0
            center_pull = (34.0 - y) * 0.22
            best = {
                "x": x,
                "y": y,
                "value": base_value,
                "objective": base_value,
            }
            for forward in [max(2.0, forward_base - 4.0), max(3.0, forward_base - 1.0), forward_base + 2.0]:
                for lateral in [-6.0, -3.0, 0.0, 3.0, 6.0]:
                    sx = _clip(x + hx * forward + px * lateral, 0.0, 104.0)
                    sy = _clip(y + hy * forward + py * lateral + center_pull * 0.35, 0.0, 68.0)
                    s_dist = math.hypot(105.0 - sx, 34.0 - sy)
                    s_angle = _shot_angle(sx, sy)
                    s_value = _shot_value(s_dist, s_angle)
                    move_cost = math.hypot(sx - x, sy - y)
                    central_bonus = 0.04 * (1.0 - min(1.0, abs(sy - 34.0) / 34.0))
                    objective = s_value + central_bonus - move_cost * 0.005
                    if objective > float(best["objective"]):
                        best = {
                            "x": sx,
                            "y": sy,
                            "value": s_value,
                            "objective": objective,
                        }
            sx = float(best["x"])
            sy = float(best["y"])
            best_value = float(best["value"])
            gain = (best_value - base_value) * 28.0
            gain = round(gain, 1)
            lane = _lane(x)
            zone = _zone(y)
            speed = math.hypot(vx, vy)
            label = _moment_label(x, y, dist, angle, vx, vy)
            tempo_note = _tempo_note(x, y, vx, vy)
            note = (
                f"{lane} · {zone} · 거리 {dist:.1f}m · 각도 {angle:.0f}° · "
                f"속도 {speed:.1f}m/s · {tempo_note} · 신뢰도 {float(item.get('conf', 0.0)) * 100:.0f}%"
            )
            overlay = None
            if clip is not None:
                ax, ay = _pitch_px((x, y), inv, clip)
                sx2, sy2 = _pitch_px((sx, sy), inv, clip)
                gx, gy = _pitch_px((105.0, 34.0), inv, clip)
                overlay = Overlay(
                    actual_px={"x": ax, "y": ay},
                    suggest_px={"x": sx2, "y": sy2},
                    goal_px={"x": gx, "y": gy},
                    angle=angle,
                    quality=quality,
                )
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
        ctx["moments"] = moments
        ctx["notes"].append(f"suggest_{len(moments)}")
        ctx["mode"] = "refined"
        return ctx

class Heat:
    key = "heat"

    def unit(self, ctx: Dict) -> Dict:
        points = ctx.get("points", [])
        moments = ctx.get("moments", [])
        clip = ctx.get("clip")
        calib = ctx.get("calib", {})
        inv = calib.get("inv")
        if not points or clip is None:
            return ctx
        rows = HEAT_ROWS
        cols = HEAT_COLS
        grid = [[0.0 for _ in range(cols)] for _ in range(rows)]
        for item in points:
            row, col = _grid_idx(float(item["x"]), float(item["y"]), rows, cols)
            grid[row][col] += float(item.get("conf", 0.0))
        suggest_grid = [[0.0 for _ in range(cols)] for _ in range(rows)]
        for moment in moments:
            row, col = _grid_idx(float(moment.suggest["x"]), float(moment.suggest["y"]), rows, cols)
            suggest_grid[row][col] += max(0.2, float(moment.conf))
        max_val = max([max(row) for row in grid] + [max(row) for row in suggest_grid] + [0.0])
        cells = _heat_cells(grid, inv, clip)
        suggest_cells = _heat_cells(suggest_grid, inv, clip)
        ctx["heatmap"] = Heatmap(
            rows=rows,
            cols=cols,
            cells=cells,
            suggest_cells=suggest_cells,
            max=max_val,
        )
        ctx["notes"].append("heatmap_ok")
        return ctx

class Pipe:
    def __init__(self, steps: List = None) -> None:
        self.steps = steps or [Link(), Calib(), Track(), Event(), Value(), Suggest(), Heat()]

    def flow(self, job_id: str, url: str, file_path: str | None = None) -> Report:
        ctx: Dict = {
            "job_id": job_id,
            "url": url,
            "notes": [],
            "mode": "basic",
            "file_path": file_path,
        }
        for step in self.steps:
            ctx = step.unit(ctx)
        moments = ctx.get("moments", [])
        status = "empty" if not moments else "ok"
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
