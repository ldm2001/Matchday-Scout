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
    const animFrameRef = useRef<number | null>(null);
    const frameRef = useRef<HTMLDivElement | null>(null);
    const containerRef = useRef<HTMLDivElement | null>(null);
    const heightRef = useRef(340);

    const maxEvents = events.length;

    // Reset when events change
    useEffect(() => {
        setCurrentEventIndex(0);
        setAnimProgress(0);
    }, [events]);

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
                        <linearGradient id="grassGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stopColor="#4ade80" stopOpacity="0.15" />
                            <stop offset="50%" stopColor="#22c55e" stopOpacity="0.1" />
                            <stop offset="100%" stopColor="#4ade80" stopOpacity="0.15" />
                        </linearGradient>
                        <filter id="glow">
                            <feGaussianBlur stdDeviation="0.8" result="coloredBlur" />
                            <feMerge>
                                <feMergeNode in="coloredBlur" />
                                <feMergeNode in="SourceGraphic" />
                            </feMerge>
                        </filter>
                        <marker id="arrowBlue" markerWidth="3" markerHeight="2" refX="2.6" refY="1" orient="auto">
                            <polygon points="0 0, 3 1, 0 2" fill="#3b82f6" />
                        </marker>
                        <marker id="arrowRed" markerWidth="3" markerHeight="2" refX="2.6" refY="1" orient="auto">
                            <polygon points="0 0, 3 1, 0 2" fill="#ef4444" />
                        </marker>
                    </defs>

                    {/* Background */}
                    <rect x={-padX} y={-padY} width={viewWidth} height={viewHeight} fill="#fafafa" />
                    <rect x={0} y={0} width={pitchWidth} height={pitchHeight} fill="url(#grassGradient)" />

                    {/* Pitch lines - softer */}
                    <rect x={0} y={0} width={pitchWidth} height={pitchHeight} fill="none" stroke="#94a3b8" strokeWidth="0.6" />
                    <line x1={pitchWidth / 2} y1={0} x2={pitchWidth / 2} y2={pitchHeight} stroke="#94a3b8" strokeWidth="0.6" />
                    <circle cx={pitchWidth / 2} cy={pitchHeight / 2} r={9.15} fill="none" stroke="#94a3b8" strokeWidth="0.6" />

                    {/* Left penalty area */}
                    <rect
                        x={0}
                        y={(pitchHeight - 40.32) / 2}
                        width="16.5"
                        height="40.32"
                        fill="none"
                        stroke="#94a3b8"
                        strokeWidth="0.6"
                    />
                    <rect
                        x={0}
                        y={(pitchHeight - 18.32) / 2}
                        width="5.5"
                        height="18.32"
                        fill="none"
                        stroke="#94a3b8"
                        strokeWidth="0.6"
                    />

                    {/* Right penalty area */}
                    <rect
                        x={pitchWidth - 16.5}
                        y={(pitchHeight - 40.32) / 2}
                        width="16.5"
                        height="40.32"
                        fill="none"
                        stroke="#94a3b8"
                        strokeWidth="0.6"
                    />
                    <rect
                        x={pitchWidth - 5.5}
                        y={(pitchHeight - 18.32) / 2}
                        width="5.5"
                        height="18.32"
                        fill="none"
                        stroke="#94a3b8"
                        strokeWidth="0.6"
                    />

                    {/* Trail lines (past events) */}
                    {visibleEvents.slice(0, -1).map((event, i) => {
                        const x1 = event.start_x;
                        const y1 = event.start_y;
                        const x2 = event.end_x;
                        const y2 = event.end_y;
                        const hasMovement = Math.abs(event.end_x - event.start_x) > 2 || Math.abs(event.end_y - event.start_y) > 2;
                        const color = '#94a3b8';

                        return hasMovement ? (
                            <line key={`trail-${i}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth="0.4" strokeDasharray="2,2" opacity="0.5" />
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
                        const color = '#3b82f6';

                        return hasMovement ? (
                            <g>
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
                                    stroke="rgba(59, 130, 246, 0.25)"
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
                                <circle cx={x} cy={y} r={1.6} fill="#cbd5e1" stroke="white" strokeWidth="0.5" />
                                <text x={x} y={y + 0.6} fill="white" fontSize="1.6" fontWeight="600" textAnchor="middle">
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
                                <circle cx={0} cy={0} r={2.4} fill="#3b82f6" stroke="white" strokeWidth="0.6" filter="url(#glow)" />
                                <text x={0} y={0.8} fill="white" fontSize="2" fontWeight="700" textAnchor="middle">
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
                                    fill="rgba(15, 23, 42, 0.8)"
                                />
                                <text
                                    x={labelX}
                                    y={labelY + 3.8}
                                    fill="white" fontSize="2" textAnchor="middle" fontWeight="500"
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
                    ⏮
                </button>

                <button
                    onClick={onPlayPause}
                    className={styles.playBtn}
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
                    <span className={styles.legendMarker} style={{ background: '#3b82f6' }}></span>
                    홈 팀
                </span>
                <span className={styles.legendItem}>
                    <span className={styles.legendMarker} style={{ background: '#ef4444' }}></span>
                    어웨이 팀
                </span>
            </div>
        </div>
    );
}
