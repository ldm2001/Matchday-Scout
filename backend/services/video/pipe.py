import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import parse_qs, urlparse

import math
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

from .model import Clip, Moment, Report

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "cache" / "video"
CACHE.mkdir(parents=True, exist_ok=True)

MAX_SEC = 90
STEP_SEC = 1
MAX_SAMPLES = 180
MIN_CONF = 0.2
MODEL = None


def _guess_profile(browser: str) -> str | None:
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


def _pick_id(url: str) -> Tuple[str, int]:
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


def _clip_from_path(path: Path) -> Clip:
    if cv2 is None:
        raise RuntimeError("opencv missing")
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    cap.release()
    name = path.stem
    return Clip(url=str(path), video_id=name, start=0, fps=fps, width=width, height=height)


def _model() -> YOLO:
    global MODEL
    if MODEL is None:
        if YOLO is None:
            raise RuntimeError("ultralytics missing")
        MODEL = YOLO("yolov8n.pt")
    return MODEL


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


class Link:
    key = "link"

    def step(self, ctx: Dict) -> Dict:
        if YoutubeDL is None:
            raise RuntimeError("yt_dlp missing")
        if ctx.get("file_path"):
            path = Path(ctx["file_path"]).expanduser().resolve()
            if not path.exists():
                raise RuntimeError("file missing")
            ctx["path"] = path
            ctx["clip"] = _clip_from_path(path)
            ctx["notes"].append("file_ok")
            return ctx
        url = ctx["url"]
        vid, start = _pick_id(url)
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
            profile = _guess_profile(browser)
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

    def step(self, ctx: Dict) -> Dict:
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
        quality = _clip(ratio * 1.6, 0.0, 1.0)
        ctx["calib"] = {"mat": mat, "quality": quality}
        ctx["notes"].append(f"calib_{quality:.2f}")
        return ctx


class Track:
    key = "track"

    def step(self, ctx: Dict) -> Dict:
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
        frame_idx = start
        while frame_idx < end_frame:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ok, frame = cap.read()
            if not ok:
                frame_idx += sample_step
                continue
            samples += 1
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = model(rgb, verbose=False)[0]
            ball = None
            ball_conf = 0.0
            player = None
            player_conf = 0.0
            for box in res.boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                if cls == 32 and conf > ball_conf:
                    ball = box.xyxy[0].cpu().numpy()
                    ball_conf = conf
                if cls == 0 and conf > player_conf:
                    player = box.xyxy[0].cpu().numpy()
                    player_conf = conf
            pick = None
            pick_conf = 0.0
            kind = "ball"
            if ball is not None and ball_conf >= MIN_CONF:
                pick = ball
                pick_conf = ball_conf
                kind = "ball"
            elif player is not None and player_conf >= MIN_CONF:
                pick = player
                pick_conf = player_conf * 0.4
                kind = "player"
            if pick is not None:
                cx = float((pick[0] + pick[2]) / 2)
                cy = float((pick[1] + pick[3]) / 2)
                if mat is not None:
                    out = _pitch(np.array([cx, cy], dtype=np.float32), mat)
                    px = _clip(out[0], 0.0, 105.0)
                    py = _clip(out[1], 0.0, 68.0)
                    conf = pick_conf * max(0.2, quality)
                else:
                    px = _norm(cx, frame.shape[1], 105.0)
                    py = _norm(cy, frame.shape[0], 68.0)
                    conf = pick_conf * 0.25
                ts = frame_idx / fps
                points.append({"ts": ts, "x": px, "y": py, "conf": conf, "kind": kind})
                if kind == "ball":
                    ball_count += 1
                else:
                    player_count += 1
            frame_idx += sample_step
        cap.release()
        ctx["points"] = points
        ctx["notes"].append(f"points_{len(points)}")
        ctx["notes"].append(f"samples_{samples}")
        ctx["notes"].append(f"ball_{ball_count}")
        ctx["notes"].append(f"player_{player_count}")
        return ctx


class Event:
    key = "event"

    def step(self, ctx: Dict) -> Dict:
        points = ctx.get("points", [])
        goal = (105.0, 34.0)
        rows = []
        for item in points:
            dist = math.hypot(goal[0] - item["x"], goal[1] - item["y"])
            score = item["conf"] * (1.0 / (1.0 + dist / 24.0))
            rows.append({
                "ts": item["ts"],
                "x": item["x"],
                "y": item["y"],
                "conf": item["conf"],
                "dist": dist,
                "score": score,
                "kind": item.get("kind", "ball"),
            })
        rows.sort(key=lambda x: x["score"], reverse=True)
        picks = []
        for row in rows:
            if row["score"] <= 0:
                continue
            if any(abs(row["ts"] - p["ts"]) < 6 for p in picks):
                continue
            picks.append(row)
            if len(picks) >= 4:
                break
        ctx["events"] = picks
        ctx["notes"].append(f"events_{len(picks)}")
        return ctx


class Value:
    key = "value"

    def step(self, ctx: Dict) -> Dict:
        events = ctx.get("events", [])
        rows = []
        for item in events:
            dist = item["dist"]
            gain = max(0.0, (60.0 - dist) / 60.0) * 7.0
            rows.append({**item, "delta": gain})
        ctx["values"] = rows
        ctx["notes"].append(f"value_{len(rows)}")
        return ctx


class Suggest:
    key = "suggest"

    def step(self, ctx: Dict) -> Dict:
        values = ctx.get("values", [])
        moments: List[Moment] = []
        for item in values:
            x = float(item["x"])
            y = float(item["y"])
            dist = float(item.get("dist", 0.0))
            forward = 6.0 if x >= 86.0 else 10.0 if x >= 78.0 else 14.0
            pull = 0.55 if abs(y - 34.0) > 12.0 else 0.4
            sx = _clip(x + forward, 0.0, 104.0)
            sy = _clip(y + (34.0 - y) * pull, 0.0, 68.0)
            angle = _shot_angle(x, y)
            lane = _lane(x)
            zone = _zone(y)
            if dist < 18.0:
                label = "유효 슈팅 찬스"
            elif dist < 30.0:
                label = "박스 진입"
            elif dist < 45.0:
                label = "공격 전개"
            else:
                label = "빌드업 진행"
            note = f"{lane} · {zone} · 거리 {dist:.1f}m · 각도 {angle:.0f}°"
            moments.append(
                Moment(
                    ts=float(item["ts"]),
                    label=label,
                    actual={"x": x, "y": y},
                    suggest={"x": sx, "y": sy},
                    delta=float(item["delta"]),
                    note=note,
                    conf=float(item["conf"]),
                )
            )
        ctx["moments"] = moments
        ctx["notes"].append(f"suggest_{len(moments)}")
        ctx["mode"] = "basic"
        return ctx


class Pipe:
    def __init__(self, steps: List = None) -> None:
        self.steps = steps or [Link(), Calib(), Track(), Event(), Value(), Suggest()]

    def run(self, job_id: str, url: str, file_path: str | None = None) -> Report:
        ctx: Dict = {
            "job_id": job_id,
            "url": url,
            "notes": [],
            "mode": "basic",
            "file_path": file_path,
        }
        for step in self.steps:
            ctx = step.step(ctx)
        moments = ctx.get("moments", [])
        status = "empty" if not moments else "ok"
        report = Report(
            job_id=job_id,
            status=status,
            clip=ctx["clip"],
            moments=moments,
            notes=ctx["notes"],
            mode=ctx.get("mode", "basic"),
        )
        return report


def pack(report: Report) -> Dict:
    data = asdict(report)
    data["clip"] = asdict(report.clip)
    data["moments"] = [asdict(item) for item in report.moments]
    return data
