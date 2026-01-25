'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { getVideoJob, startVideoJob, uploadVideoJob, VideoJob, VideoMoment } from '@/lib/api';
import styles from './VideoAnalysis.module.css';

const pickId = (url: string) => {
  try {
    const info = new URL(url);
    const host = info.hostname.toLowerCase();
    const path = info.pathname.replace(/^\/+/, '');
    if (host.includes('youtu.be')) {
      return path.split('/')[0] || '';
    }
    if (host.includes('youtube.com')) {
      if (path.startsWith('watch')) {
        return info.searchParams.get('v') || '';
      }
      if (path.startsWith('shorts/')) {
        return path.split('/')[1] || '';
      }
      if (path.startsWith('embed/')) {
        return path.split('/')[1] || '';
      }
    }
    return '';
  } catch {
    return '';
  }
};

const fmtTime = (sec: number) => {
  if (!Number.isFinite(sec)) return '--:--';
  const value = Math.max(0, Math.floor(sec));
  const min = Math.floor(value / 60);
  const rest = value % 60;
  return `${String(min).padStart(2, '0')}:${String(rest).padStart(2, '0')}`;
};

const zoneLabel = (y: number) => {
  if (y < 22.5) return '좌측';
  if (y > 45.5) return '우측';
  return '중앙';
};

const laneLabel = (x: number) => {
  if (x >= 88) return '박스 안';
  if (x >= 80) return '박스 근처';
  return '중앙 지역';
};

const shotAngle = (x: number, y: number) => {
  const left = { x: 105, y: 34 - 3.66 };
  const right = { x: 105, y: 34 + 3.66 };
  const v1 = { x: left.x - x, y: left.y - y };
  const v2 = { x: right.x - x, y: right.y - y };
  const denom = Math.hypot(v1.x, v1.y) * Math.hypot(v2.x, v2.y);
  if (denom <= 0) return 0;
  const cos = (v1.x * v2.x + v1.y * v2.y) / denom;
  const clamped = Math.max(-1, Math.min(1, cos));
  return (Math.acos(clamped) * 180) / Math.PI;
};

const moveHint = (moment: VideoMoment) => {
  const dx = moment.suggest.x - moment.actual.x;
  const dy = moment.suggest.y - moment.actual.y;
  const forward = dx >= 0 ? `전진 ${dx.toFixed(1)}m` : `후진 ${Math.abs(dx).toFixed(1)}m`;
  const lateral = Math.abs(dy) < 1 ? '좌우 이동 없음' : `${dy > 0 ? '우측' : '좌측'} ${Math.abs(dy).toFixed(1)}m`;
  return `${forward} · ${lateral}`;
};

type HeatCell = {
  row: number;
  col: number;
  value: number;
  poly_px: Array<{ x: number; y: number }>;
};

const heatPalettes: Record<string, { label: string; color: string }> = {
  sun: { label: '오렌지', color: '234, 88, 12' },
  fire: { label: '레드', color: '239, 68, 68' },
  gold: { label: '골드', color: '245, 158, 11' },
  ice: { label: '블루', color: '56, 189, 248' },
};

const suggestPalettes: Record<string, { label: string; color: string }> = {
  mint: { label: '민트', color: '16, 185, 129' },
  sky: { label: '스카이', color: '59, 130, 246' },
  violet: { label: '라벤더', color: '139, 92, 246' },
};

const packHeat = (cells: HeatCell[], rows: number, cols: number, step: number) => {
  const map = new Map<string, HeatCell>();
  cells.forEach((cell) => {
    map.set(`${cell.row}-${cell.col}`, cell);
  });
  const packed: HeatCell[] = [];
  let max = 0;
  for (let r = 0; r < rows; r += step) {
    for (let c = 0; c < cols; c += step) {
      const r1 = Math.min(rows - 1, r + step - 1);
      const c1 = Math.min(cols - 1, c + step - 1);
      let sum = 0;
      for (let rr = r; rr <= r1; rr += 1) {
        for (let cc = c; cc <= c1; cc += 1) {
          const cell = map.get(`${rr}-${cc}`);
          if (cell) sum += cell.value;
        }
      }
      const tl = map.get(`${r}-${c}`);
      const tr = map.get(`${r}-${c1}`);
      const br = map.get(`${r1}-${c1}`);
      const bl = map.get(`${r1}-${c}`);
      if (!tl || !tr || !br || !bl) continue;
      packed.push({
        row: r,
        col: c,
        value: sum,
        poly_px: [tl.poly_px[0], tr.poly_px[1], br.poly_px[2], bl.poly_px[3]],
      });
      if (sum > max) max = sum;
    }
  }
  return { cells: packed, max };
};

const statusLabel: Record<string, string> = {
  queued: '대기',
  run: '분석 중',
  ok: '완료',
  empty: '결과 없음',
  fail: '실패',
};

export default function VideoAnalysis() {
  const [url, setUrl] = useState('');
  const [job, setJob] = useState<VideoJob | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [seek, setSeek] = useState<number | null>(null);
  const [activeTs, setActiveTs] = useState<number | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [localSrc, setLocalSrc] = useState('');
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const playerHostRef = useRef<HTMLDivElement | null>(null);
  const ytPlayerRef = useRef<YT.Player | null>(null);
  const freezeRef = useRef<{ ts: number | null; until: number }>({ ts: null, until: 0 });
  const [showLines, setShowLines] = useState(true);
  const [showHeat, setShowHeat] = useState(true);
  const [showSuggestHeat, setShowSuggestHeat] = useState(false);
  const [freezeOn, setFreezeOn] = useState(true);
  const [heatStrength, setHeatStrength] = useState(90);
  const [heatStep, setHeatStep] = useState(1);
  const [heatTone, setHeatTone] = useState('sun');
  const [suggestTone, setSuggestTone] = useState('mint');
  const [manualTs, setManualTs] = useState<number | null>(null);
  const [flashOn, setFlashOn] = useState(false);
  const flashRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (flashRef.current) {
        window.clearTimeout(flashRef.current);
      }
    };
  }, []);
  const formatJobError = (message: string) => {
    const lower = message.toLowerCase();
    if (lower.includes('truncated_id') || lower.includes('incomplete youtube id')) {
      return '유튜브 링크가 올바르지 않습니다. 영상 주소를 전체로 붙여주세요.';
    }
    if (lower.includes('413') || lower.includes('body exceeded')) {
      return '업로드 용량이 너무 큽니다. 영상 길이를 줄여 다시 시도해주세요.';
    }
    if (lower.includes('failed to fetch') || lower.includes('networkerror')) {
      return '백엔드 연결에 실패했습니다. 서버 상태를 확인해주세요.';
    }
    if (lower.includes('sign in to confirm') || lower.includes('not a bot')) {
      return '유튜브 봇 확인이 필요합니다. 브라우저 로그인 쿠키를 사용해야 합니다.';
    }
    if (lower.includes('private') || lower.includes('login')) {
      return '비공개 또는 로그인 필요 영상은 분석할 수 없습니다.';
    }
    if (lower.includes('cookiesfrombrowser') || lower.includes('cookies')) {
      return '브라우저 쿠키를 읽지 못했습니다. 크롬 로그인 상태를 확인해주세요.';
    }
    if (lower.includes('yt_dlp missing')) {
      return '백엔드 분석 모듈이 설치되지 않았습니다. 서버를 재시작해주세요.';
    }
    return message;
  };
  const jobError = job?.status === 'fail' ? formatJobError(job.error || '분석에 실패했습니다.') : '';

  const videoId = useMemo(() => {
    if (job?.report?.clip?.video_id && job.report.clip.video_id.length === 11) {
      return job.report.clip.video_id;
    }
    return pickId(url);
  }, [job?.report?.clip?.video_id, url]);

  const baseStart = job?.report?.clip?.start ?? 0;
  const playerStart = seek ?? baseStart;

  const embedSrc = useMemo(() => {
    if (!videoId) return '';
    const start = Math.max(0, Math.floor(playerStart));
    return `https://www.youtube.com/embed/${videoId}?start=${start}&autoplay=1&mute=1&rel=0`;
  }, [videoId, playerStart]);

  const moments: VideoMoment[] = job?.report?.moments ?? [];
  const working = job ? ['queued', 'run'].includes(job.status) : false;
  const heatmap = job?.report?.heatmap;
  const packedHeat = useMemo(() => {
    if (!heatmap) return null;
    const base = packHeat(heatmap.cells as HeatCell[], heatmap.rows, heatmap.cols, heatStep);
    const suggest = packHeat(heatmap.suggest_cells as HeatCell[], heatmap.rows, heatmap.cols, heatStep);
    const max = Math.max(base.max, suggest.max, 0.001);
    return {
      base,
      suggest,
      max,
      rows: Math.ceil(heatmap.rows / heatStep),
      cols: Math.ceil(heatmap.cols / heatStep),
    };
  }, [heatmap, heatStep]);
  const gridLabel = (step: number) => {
    if (!heatmap) return '';
    return `${Math.ceil(heatmap.rows / step)}x${Math.ceil(heatmap.cols / step)}`;
  };
  const summary = useMemo(() => {
    if (moments.length === 0) return [];
    const zones: Record<string, number> = { 좌측: 0, 중앙: 0, 우측: 0 };
    const lanes: Record<string, number> = { '박스 안': 0, '박스 근처': 0, '중앙 지역': 0 };
    let distSum = 0;
    let angleSum = 0;
    let dxSum = 0;
    let dySum = 0;
    moments.forEach((item) => {
      const x = item.actual.x;
      const y = item.actual.y;
      zones[zoneLabel(y)] += 1;
      lanes[laneLabel(x)] += 1;
      distSum += Math.hypot(105 - x, 34 - y);
      angleSum += shotAngle(x, y);
      dxSum += item.suggest.x - x;
      dySum += item.suggest.y - y;
    });
    const total = moments.length;
    const topZone = Object.entries(zones).sort((a, b) => b[1] - a[1])[0];
    const topLane = Object.entries(lanes).sort((a, b) => b[1] - a[1])[0];
    const avgDist = distSum / total;
    const avgAngle = angleSum / total;
    const avgDx = dxSum / total;
    const avgDy = dySum / total;
    const direction = avgDy >= 0 ? '우측' : '좌측';
    const lines = [
      `${topZone[0]} 집중 ${Math.round((topZone[1] / total) * 100)}% · 주 공격 위치`,
      `${topLane[0]} 시도 ${Math.round((topLane[1] / total) * 100)}% · 평균 거리 ${avgDist.toFixed(1)}m`,
      `추천 이동 평균: 전진 ${Math.max(0, avgDx).toFixed(1)}m · ${direction} ${Math.abs(avgDy).toFixed(1)}m`,
    ];
    if (avgAngle < 12) {
      lines.push('각도 좁음 → 컷백/중앙 침투 비중 확대');
    } else if (avgAngle > 25) {
      lines.push('각도 넓음 → 빠른 마무리 빈도 확대');
    }
    return lines;
  }, [moments]);

  const run = async () => {
    if (!url.trim() && !file) {
      setErr('유튜브 링크를 입력하거나 파일을 선택해주세요.');
      return;
    }
    if (!file) {
      const trimmed = url.trim();
      const id = pickId(trimmed);
      if (!id || id.length < 11) {
        setErr('유튜브 링크가 올바르지 않습니다. 전체 주소를 입력해주세요.');
        return;
      }
    }
    setErr('');
    setBusy(true);
    try {
      const data = file ? await uploadVideoJob(file, url.trim()) : await startVideoJob(url.trim());
      setJob(data);
      setSeek(null);
      setActiveTs(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : '분석 요청에 실패했습니다.';
      setErr(formatJobError(message));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (!file) {
      setLocalSrc('');
      return;
    }
    const nextUrl = URL.createObjectURL(file);
    setLocalSrc(nextUrl);
    return () => URL.revokeObjectURL(nextUrl);
  }, [file]);

  useEffect(() => {
    if (!job) return;
    if (!['queued', 'run'].includes(job.status)) return;
    const timer = setInterval(async () => {
      try {
        const fresh = await getVideoJob(job.job_id);
        setJob(fresh);
      } catch {
        clearInterval(timer);
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [job?.job_id, job?.status]);

  const handlePick = (ts: number) => {
    setSeek(ts);
    setActiveTs(ts);
    setManualTs(ts);
    setFlashOn(true);
    if (flashRef.current) {
      window.clearTimeout(flashRef.current);
    }
    flashRef.current = window.setTimeout(() => setFlashOn(false), 1400);
    if (videoRef.current) {
      videoRef.current.currentTime = ts;
      const promise = videoRef.current.play();
      if (promise && typeof promise.catch === 'function') {
        promise.catch(() => {});
      }
      return;
    }
    if (ytPlayerRef.current) {
      ytPlayerRef.current.seekTo(ts, true);
      ytPlayerRef.current.playVideo();
    }
  };

  useEffect(() => {
    if (!localSrc || !videoRef.current || moments.length === 0) return;
    const video = videoRef.current;
    const onTime = () => {
      const current = video.currentTime;
      if (manualTs !== null) {
        if (Math.abs(current - manualTs) > 2.5) {
          setManualTs(null);
        } else {
          setActiveTs(manualTs);
          return;
        }
      }
      let best: VideoMoment | null = null;
      let bestDiff = 2.0;
      for (const item of moments) {
        const diff = Math.abs(item.ts - current);
        if (diff <= bestDiff) {
          best = item;
          bestDiff = diff;
        }
      }
      if (best && best.ts !== activeTs) {
        setActiveTs(best.ts);
        setFlashOn(true);
        if (flashRef.current) {
          window.clearTimeout(flashRef.current);
        }
        flashRef.current = window.setTimeout(() => setFlashOn(false), 900);
      }
    };
    video.addEventListener('timeupdate', onTime);
    return () => video.removeEventListener('timeupdate', onTime);
  }, [localSrc, moments, manualTs, activeTs]);

  useEffect(() => {
    if (localSrc) return;
    if (!videoId || !playerHostRef.current) return;
    let cancelled = false;
    const load = () =>
      new Promise<void>((resolve) => {
        if (window.YT && window.YT.Player) {
          resolve();
          return;
        }
        const script = document.createElement('script');
        script.src = 'https://www.youtube.com/iframe_api';
        document.body.appendChild(script);
        (window as any).onYouTubeIframeAPIReady = () => resolve();
      });
    load().then(() => {
      if (cancelled) return;
      if (ytPlayerRef.current) {
        ytPlayerRef.current.destroy();
      }
      ytPlayerRef.current = new window.YT.Player(playerHostRef.current as HTMLDivElement, {
        videoId,
        playerVars: {
          rel: 0,
          modestbranding: 1,
          controls: 1,
          start: Math.floor(baseStart),
        },
        events: {
          onReady: (event) => {
            if (seek !== null) {
              event.target.seekTo(seek, true);
            }
          },
        },
      });
    });
    return () => {
      cancelled = true;
      if (ytPlayerRef.current) {
        ytPlayerRef.current.destroy();
        ytPlayerRef.current = null;
      }
    };
  }, [videoId, localSrc, baseStart, seek]);

  useEffect(() => {
    if (localSrc || !ytPlayerRef.current || moments.length === 0) return;
    const timer = setInterval(() => {
      const player = ytPlayerRef.current;
      if (!player || typeof player.getCurrentTime !== 'function') return;
      const current = player.getCurrentTime();
      if (manualTs !== null) {
        if (Math.abs(current - manualTs) > 2.5) {
          setManualTs(null);
        } else {
          setActiveTs(manualTs);
          return;
        }
      }
      let best: VideoMoment | null = null;
      let bestDiff = 2.0;
      for (const item of moments) {
        const diff = Math.abs(item.ts - current);
        if (diff <= bestDiff) {
          best = item;
          bestDiff = diff;
        }
      }
      if (best && best.ts !== activeTs) {
        setActiveTs(best.ts);
        setFlashOn(true);
        if (flashRef.current) {
          window.clearTimeout(flashRef.current);
        }
        flashRef.current = window.setTimeout(() => setFlashOn(false), 900);
      }
    }, 300);
    return () => clearInterval(timer);
  }, [localSrc, moments, manualTs, activeTs]);

  const activeMoment = useMemo(() => {
    if (activeTs === null) return null;
    const found = moments.find((item) => Math.abs(item.ts - activeTs) < 0.01);
    return found || null;
  }, [activeTs, moments]);
  const tacticLine = useMemo(() => {
    if (!activeMoment) return '';
    const x = activeMoment.actual.x;
    const y = activeMoment.actual.y;
    const dist = Math.hypot(105 - x, 34 - y);
    const angle = shotAngle(x, y);
    return `${laneLabel(x)} · ${zoneLabel(y)} · ${dist.toFixed(1)}m · ${angle.toFixed(0)}° · ${moveHint(activeMoment)}`;
  }, [activeMoment]);

  const overlayVisible = !!activeMoment && (manualTs !== null || flashOn);

  useEffect(() => {
    if (!localSrc && !videoId) return;
    if (!canvasRef.current) return;
    const moment = activeMoment;
    const overlay = moment?.overlay;
    const canvas = canvasRef.current;
    const video = videoRef.current;
    const rect = localSrc
      ? video?.getBoundingClientRect()
      : playerHostRef.current?.getBoundingClientRect();
    if (!rect) return;
    if ((!overlay && !packedHeat) || rect.width === 0 || rect.height === 0) {
      const ctx = canvas.getContext('2d');
      if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${rect.height}px`;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);
    const clipW = job?.report?.clip?.width || video?.videoWidth || rect.width;
    const clipH = job?.report?.clip?.height || video?.videoHeight || rect.height;
    const scaleX = rect.width / clipW;
    const scaleY = rect.height / clipH;
    const toScreen = (pt: { x: number; y: number }) => ({
      x: pt.x * scaleX,
      y: pt.y * scaleY,
    });
    const actual = overlay ? toScreen(overlay.actual_px) : null;
    const suggest = overlay ? toScreen(overlay.suggest_px) : null;
    const goal = overlay ? toScreen(overlay.goal_px) : null;

    if (showHeat && packedHeat?.base.cells && packedHeat.max > 0) {
      const color = heatPalettes[heatTone]?.color || heatPalettes.sun.color;
      const strength = Math.max(0.1, heatStrength / 100);
      packedHeat.base.cells.forEach((cell) => {
        if (cell.value <= 0) return;
        const alpha = Math.min(0.7, 0.06 + (cell.value / packedHeat.max) * 0.5 * strength);
        ctx.fillStyle = `rgba(${color}, ${alpha})`;
        ctx.beginPath();
        cell.poly_px.forEach((pt, idx) => {
          const screen = toScreen(pt);
          if (idx === 0) ctx.moveTo(screen.x, screen.y);
          else ctx.lineTo(screen.x, screen.y);
        });
        ctx.closePath();
        ctx.fill();
      });
    }

    if (showSuggestHeat && packedHeat?.suggest.cells && packedHeat.max > 0) {
      const color = suggestPalettes[suggestTone]?.color || suggestPalettes.mint.color;
      const strength = Math.max(0.1, heatStrength / 100);
      packedHeat.suggest.cells.forEach((cell) => {
        if (cell.value <= 0) return;
        const alpha = Math.min(0.6, 0.05 + (cell.value / packedHeat.max) * 0.45 * strength);
        ctx.fillStyle = `rgba(${color}, ${alpha})`;
        ctx.beginPath();
        cell.poly_px.forEach((pt, idx) => {
          const screen = toScreen(pt);
          if (idx === 0) ctx.moveTo(screen.x, screen.y);
          else ctx.lineTo(screen.x, screen.y);
        });
        ctx.closePath();
        ctx.fill();
      });
    }

    if (overlayVisible && showLines && actual && suggest && goal) {
      ctx.lineCap = 'round';
      ctx.lineWidth = 3;
      ctx.strokeStyle = '#ef4444';
      ctx.beginPath();
      ctx.moveTo(actual.x, actual.y);
      ctx.lineTo(goal.x, goal.y);
      ctx.stroke();

      ctx.strokeStyle = '#16a34a';
      ctx.beginPath();
      ctx.moveTo(suggest.x, suggest.y);
      ctx.lineTo(goal.x, goal.y);
      ctx.stroke();

      ctx.strokeStyle = '#f59e0b';
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(actual.x, actual.y);
      ctx.lineTo(suggest.x, suggest.y);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    const drawPoint = (pt: { x: number; y: number }, color: string) => {
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();
    };
    if (overlayVisible && actual && suggest) {
      drawPoint(actual, '#ef4444');
      drawPoint(suggest, '#16a34a');

      ctx.fillStyle = '#0f172a';
      ctx.font = '12px IBM Plex Sans KR, sans-serif';
      if (overlay) {
        ctx.fillText(`${overlay.angle.toFixed(0)}°`, actual.x + 8, actual.y - 8);
      }
      ctx.fillStyle = '#ef4444';
      ctx.fillText('실제', actual.x + 8, actual.y + 14);
      ctx.fillStyle = '#16a34a';
      ctx.fillText('추천', suggest.x + 8, suggest.y + 14);
    }
  }, [
    activeMoment,
    localSrc,
    videoId,
    packedHeat,
    showHeat,
    showSuggestHeat,
    showLines,
    overlayVisible,
    heatStrength,
    heatTone,
    suggestTone,
    job?.report?.clip?.width,
    job?.report?.clip?.height,
  ]);

  useEffect(() => {
    if (!freezeOn || !activeMoment) return;
    const now = Date.now();
    if (freezeRef.current.ts === activeMoment.ts && now < freezeRef.current.until) return;
    freezeRef.current = { ts: activeMoment.ts, until: now + 1200 };
    if (videoRef.current) {
      videoRef.current.pause();
      setTimeout(() => {
        const promise = videoRef.current?.play();
        if (promise && typeof promise.catch === 'function') {
          promise.catch(() => {});
        }
      }, 900);
      return;
    }
    if (ytPlayerRef.current) {
      ytPlayerRef.current.pauseVideo();
      setTimeout(() => {
        ytPlayerRef.current?.playVideo();
      }, 900);
    }
  }, [activeMoment, freezeOn]);

  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <div>
          <div className={styles.title}>영상 분석</div>
          <div className={styles.sub}>유튜브 링크를 붙여넣으면 장면별 분석을 표시합니다.</div>
        </div>
        <div className={styles.status}>
          <span className={styles.statusBadge}>
            {job ? statusLabel[job.status] || job.status : '대기'}
          </span>
          {job?.report?.mode === 'stub' && (
            <span className={styles.statusNote}>모델 연결 준비 중</span>
          )}
        </div>
      </div>

      <div className={styles.form}>
        <input
          className={styles.input}
          placeholder="https://www.youtube.com/watch?v=..."
          value={url}
          onChange={(event) => setUrl(event.target.value)}
        />
        <label className={styles.uploadButton}>
          <input
            type="file"
            accept="video/mp4,video/quicktime,video/x-matroska"
            onChange={(event) => {
              const picked = event.target.files?.[0] || null;
              setFile(picked);
            }}
            className={styles.uploadInput}
          />
          {file ? file.name : '파일 선택'}
        </label>
        <button className={styles.button} onClick={run} disabled={busy}>
          {busy ? '요청 중' : '분석 시작'}
        </button>
      </div>
      <div className={styles.controls}>
        <label className={styles.controlItem}>
          <input
            type="checkbox"
            checked={showLines}
            onChange={(event) => setShowLines(event.target.checked)}
          />
          라인/각도
        </label>
        <label className={styles.controlItem}>
          <input
            type="checkbox"
            checked={showHeat}
            onChange={(event) => setShowHeat(event.target.checked)}
          />
          히트맵
        </label>
        <label className={styles.controlItem}>
          <input
            type="checkbox"
            checked={showSuggestHeat}
            onChange={(event) => setShowSuggestHeat(event.target.checked)}
          />
          디버전시
        </label>
        <label className={styles.controlItem}>
          <input
            type="checkbox"
            checked={freezeOn}
            onChange={(event) => setFreezeOn(event.target.checked)}
          />
          프리즈
        </label>
        <label className={`${styles.controlItem} ${styles.controlRange}`}>
          강도
          <input
            type="range"
            min={40}
            max={140}
            value={heatStrength}
            onChange={(event) => setHeatStrength(Number(event.target.value))}
          />
          <span className={styles.controlValue}>{heatStrength}%</span>
        </label>
        <label className={styles.controlItem}>
          그리드
          <select
            value={heatStep}
            onChange={(event) => setHeatStep(Number(event.target.value))}
            className={styles.controlSelect}
          >
            <option value={1}>촘촘 {gridLabel(1)}</option>
            <option value={2}>중간 {gridLabel(2)}</option>
            <option value={4}>크게 {gridLabel(4)}</option>
          </select>
        </label>
        <label className={styles.controlItem}>
          히트맵 색
          <select
            value={heatTone}
            onChange={(event) => setHeatTone(event.target.value)}
            className={styles.controlSelect}
          >
            {Object.entries(heatPalettes).map(([key, val]) => (
              <option key={key} value={key}>{val.label}</option>
            ))}
          </select>
        </label>
        <label className={styles.controlItem}>
          디버전시 색
          <select
            value={suggestTone}
            onChange={(event) => setSuggestTone(event.target.value)}
            className={styles.controlSelect}
          >
            {Object.entries(suggestPalettes).map(([key, val]) => (
              <option key={key} value={key}>{val.label}</option>
            ))}
          </select>
        </label>
      </div>
      {err && <div className={styles.error}>{err}</div>}
      {jobError && <div className={styles.error}>{jobError}</div>}

      <div className={styles.main}>
        <div className={styles.player}>
          {localSrc ? (
            <>
              <video
                ref={videoRef}
                className={styles.playerFrame}
                src={localSrc}
                controls
              />
              <canvas ref={canvasRef} className={styles.overlay} />
              {overlayVisible && tacticLine && (
                <div className={styles.tacticCard} title={tacticLine}>
                  {tacticLine}
                </div>
              )}
            </>
          ) : embedSrc ? (
            <>
              <div ref={playerHostRef} className={styles.playerFrame} />
              <canvas ref={canvasRef} className={styles.overlay} />
              {overlayVisible && tacticLine && (
                <div className={styles.tacticCard} title={tacticLine}>
                  {tacticLine}
                </div>
              )}
            </>
          ) : (
            <div className={styles.placeholder}>링크를 입력하면 영상이 표시됩니다.</div>
          )}
        </div>

        <div className={styles.panel}>
          <div className={styles.panelTitle}>타임라인</div>
          {summary.length > 0 && (
            <div className={styles.summary}>
              <div className={styles.summaryTitle}>전술 요약</div>
              {summary.map((line) => (
                <div key={line} className={styles.summaryItem}>
                  <span className={styles.summaryDot} />
                  <span>{line}</span>
                </div>
              ))}
            </div>
          )}
          {moments.length === 0 ? (
            <div className={styles.empty}>
              {working ? '분석 중입니다. 잠시만 기다려주세요.' : '분석 결과가 없습니다. 링크를 확인해주세요.'}
            </div>
          ) : (
            <div className={styles.list}>
              {moments.map((item) => {
                const delta = Number.isFinite(item.delta) ? item.delta : 0;
                return (
                  <button
                    key={`${item.ts}-${item.label}`}
                    className={`${styles.item} ${activeTs === item.ts ? styles.itemActive : ''}`}
                    onClick={() => handlePick(item.ts)}
                  >
                    <div className={styles.itemTime}>{fmtTime(item.ts)}</div>
                    <div className={styles.itemMain}>
                      <div className={styles.itemTitle}>{item.label || '장면'}</div>
                      <div className={styles.itemNote}>{item.note || '상황 설명 없음'}</div>
                      <div className={styles.itemMove}>추천 이동: {moveHint(item)}</div>
                    </div>
                    <div className={`${styles.itemDelta} ${delta < 0 ? styles.itemDeltaNeg : ''}`}>
                      {delta >= 0 ? `+${delta.toFixed(1)}%p` : `${delta.toFixed(1)}%p`}
                    </div>
                  </button>
                );
              })}
            </div>
          )}

        </div>
      </div>

      <div className={styles.license}>
        영상 저작권은 각 권리자에게 있으며, 본 서비스는 YouTube 이용약관을 준수합니다. 분석 결과는 참고용입니다.
      </div>
    </div>
  );
}
