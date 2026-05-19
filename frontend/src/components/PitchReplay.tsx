// 피치 리플레이 컴포넌트 - 공격 페이즈 이벤트를 애니메이션으로 재생
'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { ReplayEvent } from '@/types';
import styles from './PitchReplay.module.css';

interface PitchReplayProps {
    events: ReplayEvent[];
    isPlaying: boolean;
    onPlayPause: () => void;
    playbackSpeed: number;
    onSpeedChange: (speed: number) => void;
}

// SVG 피치 위에 이벤트 순서대로 마커와 경로 표시, 재생/일시정지/속도 조절 지원
export default function PitchReplay({
    events,
    isPlaying,
    onPlayPause,
    playbackSpeed,
    onSpeedChange,
}: PitchReplayProps) {
    const [currentEventIndex, setCurrentEventIndex] = useState(0);
    const [animProgress, setAnimProgress] = useState(0);
    const [fieldHeight, setFieldHeight] = useState(320);
    const [prevEvents, setPrevEvents] = useState(events);
    const animFrameRef = useRef<number | null>(null);
    const frameRef = useRef<HTMLDivElement | null>(null);
    const containerRef = useRef<HTMLDivElement | null>(null);
    const heightRef = useRef(340);

    const maxEvents = events.length;

    // events 변경 시 렌더 타이밍에 진행도 초기화 (useEffect 안에서 setState 지양)
    if (prevEvents !== events) {
        setPrevEvents(events);
        setCurrentEventIndex(0);
        setAnimProgress(0);
    }

    // Smooth animation with requestAnimationFrame
    useEffect(() => {
        if (isPlaying && events.length > 0) {
            const frameDuration = 600 / playbackSpeed; // Total time per event
            let startTime: number | null = null;

            const animate = (timestamp: number) => {
                if (!startTime) startTime = timestamp;
                const elapsed = timestamp - startTime;
                const progress = Math.min(elapsed / frameDuration, 1);

                setAnimProgress(progress);

                if (progress < 1) {
                    animFrameRef.current = requestAnimationFrame(animate);
                } else {
                    // Move to next event
                    setCurrentEventIndex((prev) => {
                        if (prev >= maxEvents - 1) {
                            setTimeout(() => onPlayPause(), 0);
                            return 0;
                        }
                        return prev + 1;
                    });
                    startTime = null;
                    setAnimProgress(0);
                    if (isPlaying) {
                        animFrameRef.current = requestAnimationFrame(animate);
                    }
                }
            };

            animFrameRef.current = requestAnimationFrame(animate);
        }

        return () => {
            if (animFrameRef.current) {
                cancelAnimationFrame(animFrameRef.current);
            }
        };
    }, [isPlaying, playbackSpeed, maxEvents, onPlayPause, events.length, currentEventIndex]);

    const handleReset = useCallback(() => {
        setCurrentEventIndex(0);
        setAnimProgress(0);
    }, []);

    // Pitch units (meters) + padded view that preserves ratio
    const pitchWidth = 105;
    const pitchHeight = 68;
    const padX = 4;
    const padY = (padX * pitchHeight) / pitchWidth;
    const viewWidth = pitchWidth + padX * 2;
    const viewHeight = pitchHeight + padY * 2;

    useEffect(() => {
        if (!containerRef.current || typeof ResizeObserver === 'undefined') return;
        const node = containerRef.current;
        const uiHeight = 132;
        const sync = () => {
            const width = node.clientWidth;
            const height = node.clientHeight;
            if (!width || !height) return;
            const ideal = (width * pitchHeight) / pitchWidth;
            const available = Math.max(0, height - uiHeight);
            const next = Math.round(Math.min(460, Math.max(300, Math.min(ideal, available))));
            if (Math.abs(next - heightRef.current) > 1) {
                heightRef.current = next;
                setFieldHeight(next);
            }
        };
        sync();
        const observer = new ResizeObserver(sync);
        observer.observe(node);
        return () => observer.disconnect();
    }, [pitchHeight, pitchWidth]);

    const visibleEvents = events.slice(0, currentEventIndex + 1);
    const currentEvent = events[currentEventIndex];

    if (events.length === 0) {
        return (
            <div className={styles.emptyState}>
                리플레이 데이터가 없습니다
            </div>
        );
    }

    // Easing function for smooth animation
    const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);

    return (
        <div ref={containerRef} className={styles.container}>
            {/* Pitch SVG with fixed height */}
            <div
                ref={frameRef}
                className={styles.svgFrame}
                style={{ height: fieldHeight }}>
                <svg
                    viewBox={`${-padX} ${-padY} ${viewWidth} ${viewHeight}`}
                    className={styles.svgArea}
                    preserveAspectRatio="xMidYMid meet"
                >
                    {/* Gradient grass background */}
                    <defs>
                        <linearGradient id="grassGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                            <stop offset="0%" stopColor="#4a8b3a" />
                            <stop offset="55%" stopColor="#3d7a2e" />
                            <stop offset="100%" stopColor="#2f6024" />
                        </linearGradient>
                        <pattern id="grassStripe" width="7" height="68" patternUnits="userSpaceOnUse">
                            <rect width="3.5" height="68" fill="rgba(255,255,255,0.045)" />
                            <rect x="3.5" width="3.5" height="68" fill="rgba(0,0,0,0.04)" />
                        </pattern>
                        <filter id="glow">
                            <feGaussianBlur stdDeviation="0.8" result="coloredBlur" />
                            <feMerge>
                                <feMergeNode in="coloredBlur" />
                                <feMergeNode in="SourceGraphic" />
                            </feMerge>
                        </filter>
                        <marker id="arrowBlue" markerWidth="3" markerHeight="2" refX="2.6" refY="1" orient="auto">
                            <polygon points="0 0, 3 1, 0 2" fill="#fbbf24" />
                        </marker>
                        <marker id="arrowRed" markerWidth="3" markerHeight="2" refX="2.6" refY="1" orient="auto">
                            <polygon points="0 0, 3 1, 0 2" fill="#ef4444" />
                        </marker>
                    </defs>

                    {/* Background */}
                    <rect x={-padX} y={-padY} width={viewWidth} height={viewHeight} fill="#0f1f10" />
                    <rect x={0} y={0} width={pitchWidth} height={pitchHeight} fill="url(#grassGradient)" />
                    <rect x={0} y={0} width={pitchWidth} height={pitchHeight} fill="url(#grassStripe)" />

                    {/* Pitch lines - white K-League style */}
                    <rect x={0} y={0} width={pitchWidth} height={pitchHeight} fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth="0.22" />
                    <line x1={pitchWidth / 2} y1={0} x2={pitchWidth / 2} y2={pitchHeight} stroke="rgba(255,255,255,0.85)" strokeWidth="0.22" />
                    <circle cx={pitchWidth / 2} cy={pitchHeight / 2} r={9.15} fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth="0.22" />
                    <circle cx={pitchWidth / 2} cy={pitchHeight / 2} r="0.5" fill="rgba(255,255,255,0.85)" />

                    {/* Left penalty area */}
                    <rect
                        x={0}
                        y={(pitchHeight - 40.32) / 2}
                        width="16.5"
                        height="40.32"
                        fill="none"
                        stroke="rgba(255,255,255,0.85)"
                        strokeWidth="0.22"
                    />
                    <rect
                        x={0}
                        y={(pitchHeight - 18.32) / 2}
                        width="5.5"
                        height="18.32"
                        fill="none"
                        stroke="rgba(255,255,255,0.85)"
                        strokeWidth="0.22"
                    />
                    <circle cx="11" cy={pitchHeight / 2} r="0.5" fill="rgba(255,255,255,0.85)" />

                    {/* Right penalty area */}
                    <rect
                        x={pitchWidth - 16.5}
                        y={(pitchHeight - 40.32) / 2}
                        width="16.5"
                        height="40.32"
                        fill="none"
                        stroke="rgba(255,255,255,0.85)"
                        strokeWidth="0.22"
                    />
                    <rect
                        x={pitchWidth - 5.5}
                        y={(pitchHeight - 18.32) / 2}
                        width="5.5"
                        height="18.32"
                        fill="none"
                        stroke="rgba(255,255,255,0.85)"
                        strokeWidth="0.22"
                    />
                    <circle cx={pitchWidth - 11} cy={pitchHeight / 2} r="0.5" fill="rgba(255,255,255,0.85)" />

                    {/* Penalty arcs */}
                    <path d={`M 16.5 ${pitchHeight / 2 - 7.31} A 9.15 9.15 0 0 1 16.5 ${pitchHeight / 2 + 7.31}`} fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth="0.22" />
                    <path d={`M ${pitchWidth - 16.5} ${pitchHeight / 2 - 7.31} A 9.15 9.15 0 0 0 ${pitchWidth - 16.5} ${pitchHeight / 2 + 7.31}`} fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth="0.22" />

                    {/* Corner arcs */}
                    <path d="M 0 1 A 1 1 0 0 1 1 0" fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth="0.22" />
                    <path d={`M ${pitchWidth - 1} 0 A 1 1 0 0 1 ${pitchWidth} 1`} fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth="0.22" />
                    <path d={`M 0 ${pitchHeight - 1} A 1 1 0 0 0 1 ${pitchHeight}`} fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth="0.22" />
                    <path d={`M ${pitchWidth} ${pitchHeight - 1} A 1 1 0 0 0 ${pitchWidth - 1} ${pitchHeight}`} fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth="0.22" />

                    {/* Corner red dots */}
                    <circle cx="0" cy="0" r="0.85" fill="#ef4444" />
                    <circle cx={pitchWidth} cy="0" r="0.85" fill="#ef4444" />
                    <circle cx="0" cy={pitchHeight} r="0.85" fill="#ef4444" />
                    <circle cx={pitchWidth} cy={pitchHeight} r="0.85" fill="#ef4444" />

                    {/* Trail lines (past events) */}
                    {visibleEvents.slice(0, -1).map((event, i) => {
                        const x1 = event.start_x;
                        const y1 = event.start_y;
                        const x2 = event.end_x;
                        const y2 = event.end_y;
                        const hasMovement = Math.abs(event.end_x - event.start_x) > 2 || Math.abs(event.end_y - event.start_y) > 2;
                        const color = 'rgba(255,255,255,0.42)';

                        return hasMovement ? (
                            <line key={`trail-${i}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth="0.4" strokeDasharray="2,2" opacity="0.6" />
                        ) : null;
                    })}

                    {/* Current event line with animation */}
                    {currentEvent && (() => {
                        const x1 = currentEvent.start_x;
                        const y1 = currentEvent.start_y;
                        const x2 = currentEvent.end_x;
                        const y2 = currentEvent.end_y;
                        const hasMovement = Math.abs(currentEvent.end_x - currentEvent.start_x) > 2 || Math.abs(currentEvent.end_y - currentEvent.start_y) > 2;

                        const easedProgress = easeOutCubic(animProgress);
                        const currentX2 = x1 + (x2 - x1) * easedProgress;
                        const currentY2 = y1 + (y2 - y1) * easedProgress;
                        const ripple = Math.sin(easedProgress * Math.PI);
                        const headScale = 1 + ripple * 0.2;
                        const color = '#fbbf24';

                        return hasMovement ? (
                            <g>
                                <line
                                    x1={x1} y1={y1}
                                    x2={currentX2} y2={currentY2}
                                    stroke="rgba(0,0,0,0.45)"
                                    strokeWidth="1.4"
                                    strokeLinecap="round"
                                />
                                <line
                                    x1={x1} y1={y1}
                                    x2={currentX2} y2={currentY2}
                                    stroke={color}
                                    strokeWidth="0.9"
                                    strokeLinecap="round"
                                    markerEnd="url(#arrowBlue)"
                                    filter="url(#glow)"
                                />
                                <circle
                                    cx={currentX2}
                                    cy={currentY2}
                                    r={2.2 * headScale}
                                    fill={color}
                                    stroke="white"
                                    strokeWidth="0.6"
                                    filter="url(#glow)"
                                />
                                <circle
                                    cx={currentX2}
                                    cy={currentY2}
                                    r={5 * ripple}
                                    fill="none"
                                    stroke="rgba(251, 191, 36, 0.55)"
                                    strokeWidth="0.6"
                                />
                            </g>
                        ) : null;
                    })()}

                    {/* Past markers (smaller, faded) */}
                    {visibleEvents.slice(0, -1).map((event, i) => {
                        const x = event.start_x;
                        const y = event.start_y;

                        return (
                            <g key={`pastMarker-${i}`}>
                                <circle cx={x} cy={y} r={1.6} fill="rgba(255,255,255,0.85)" stroke="rgba(0,0,0,0.4)" strokeWidth="0.4" />
                                <text x={x} y={y + 0.6} fill="#0f172a" fontSize="1.6" fontWeight="700" textAnchor="middle">
                                    {i + 1}
                                </text>
                            </g>
                        );
                    })}

                    {/* Current marker (animated, highlighted) */}
                    {currentEvent && (() => {
                        const x = currentEvent.start_x;
                        const y = currentEvent.start_y;
                        const pulseScale = 1 + Math.sin(animProgress * Math.PI) * 0.15;

                        return (
                            <g transform={`translate(${x} ${y}) scale(${pulseScale})`}>
                                <circle cx={0} cy={0} r={3.6} fill="rgba(251, 191, 36, 0.18)" />
                                <circle cx={0} cy={0} r={2.4} fill="#fbbf24" stroke="white" strokeWidth="0.6" filter="url(#glow)" />
                                <text x={0} y={0.8} fill="#0f172a" fontSize="2" fontWeight="800" textAnchor="middle">
                                    {currentEventIndex + 1}
                                </text>
                            </g>
                        );
                    })()}

                    {/* Action label */}
                    {currentEvent && (() => {
                        const labelWidth = Math.min(28, Math.max(16, (currentEvent.type?.length || 4) * 1.8));
                        const halfWidth = labelWidth / 2;
                        const edgeNudge =
                            currentEvent.start_x < 12 ? 6 :
                                currentEvent.start_x > pitchWidth - 12 ? -6 : 0;
                        const labelX = Math.min(
                            Math.max(currentEvent.start_x + edgeNudge, halfWidth + 0.8),
                            pitchWidth - halfWidth - 0.8
                        );
                        const labelHeight = 5.5;
                        const markerR = 2.4;
                        const gap = 2.8;
                        const needsBelow = currentEvent.start_y < (labelHeight + markerR + gap + 0.6);
                        const baseY = needsBelow
                            ? currentEvent.start_y + markerR + gap
                            : currentEvent.start_y - (labelHeight + markerR + gap);
                        const labelMin = 1;
                        const labelMax = pitchHeight - labelHeight - 0.8;
                        const labelY = Math.min(Math.max(baseY, labelMin), labelMax);
                        return (
                            <g>
                                <rect
                                    x={labelX - halfWidth}
                                    y={labelY}
                                    width={labelWidth} height="5.5" rx="1.2"
                                    fill="rgba(0, 0, 0, 0.78)"
                                    stroke="rgba(255,255,255,0.18)"
                                    strokeWidth="0.18"
                                />
                                <text
                                    x={labelX}
                                    y={labelY + 3.8}
                                    fill="white" fontSize="2" textAnchor="middle" fontWeight="600"
                                >
                                    {currentEvent.type}
                                </text>
                            </g>
                        );
                    })()}
                </svg>
            </div>

            {/* Current event info */}
            <div className={styles.eventInfo}>
                <span className={styles.playerName}>
                    {currentEvent?.player || '선수'}
                </span>
                <span className={styles.dotSep}>·</span>
                <span className={styles.actionType}>{currentEvent?.type || '액션'}</span>
                {currentEvent?.position && currentEvent.position !== 'nan' && (
                    <>
                        <span className={styles.dotSep}>·</span>
                        <span className={styles.actionPos}>{currentEvent.position}</span>
                    </>
                )}
            </div>

            {/* Controls */}
            <div className={styles.controlsWrap}>
                <button
                    onClick={handleReset}
                    className={styles.resetBtn}
                >
                    처음
                </button>

                <button
                    onClick={onPlayPause}
                    className={styles.playBtn}
                    aria-label={isPlaying ? '정지' : '재생'}
                >
                    {isPlaying ? '⏸' : '▶'}
                </button>

                <div className={styles.speedGroup}>
                    {[0.5, 1, 2].map((speed) => (
                        <button
                            key={speed}
                            onClick={() => onSpeedChange(speed)}
                            className={`${styles.speedBtn} ${playbackSpeed === speed ? styles.speedBtnActive : styles.speedBtnInactive}`}
                        >
                            {speed}x
                        </button>
                    ))}
                </div>

                <span className={styles.counterTxt}>
                    {currentEventIndex + 1} / {events.length}
                </span>
            </div>

            {/* Legend */}
            <div className={styles.legendWrap}>
                <span className={styles.legendItem}>
                    <span className={`${styles.legendMarker} ${styles.legendMarkerCurrent}`}></span>
                    현재 이벤트
                </span>
                <span className={styles.legendItem}>
                    <span className={`${styles.legendMarker} ${styles.legendMarkerPast}`}></span>
                    지나간 이벤트
                </span>
            </div>
        </div>
    );
}
