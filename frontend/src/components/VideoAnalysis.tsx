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
  const notes = job?.report?.notes ?? [];
  const working = job ? ['queued', 'run'].includes(job.status) : false;

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
    if (videoRef.current) {
      videoRef.current.currentTime = ts;
      void videoRef.current.play();
    }
  };

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
      {err && <div className={styles.error}>{err}</div>}
      {jobError && <div className={styles.error}>{jobError}</div>}

      <div className={styles.main}>
        <div className={styles.player}>
          {localSrc ? (
            <video
              ref={videoRef}
              className={styles.playerFrame}
              src={localSrc}
              controls
            />
          ) : embedSrc ? (
            <iframe
              className={styles.playerFrame}
              src={embedSrc}
              title="video-analysis"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
            />
          ) : (
            <div className={styles.placeholder}>링크를 입력하면 영상이 표시됩니다.</div>
          )}
        </div>

        <div className={styles.panel}>
          <div className={styles.panelTitle}>타임라인</div>
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
                    </div>
                    <div className={`${styles.itemDelta} ${delta < 0 ? styles.itemDeltaNeg : ''}`}>
                      {delta >= 0 ? `+${delta.toFixed(1)}%p` : `${delta.toFixed(1)}%p`}
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          {notes.length > 0 && (
            <div className={styles.note}>
              {notes.join(' · ')}
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
