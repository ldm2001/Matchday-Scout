'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { ReplayEvent } from '@/types';

interface PitchReplayProps {
    events: ReplayEvent[];
    isPlaying: boolean;
    onPlayPause: () => void;
    playbackSpeed: number;
    onSpeedChange: (speed: number) => void;
}

export default function PitchReplay({
    events,
    isPlaying,
    onPlayPause,
    playbackSpeed,
    onSpeedChange,
}: PitchReplayProps) {
    const [currentEventIndex, setCurrentEventIndex] = useState(0);
    const [animProgress, setAnimProgress] = useState(0);
    const intervalRef = useRef<NodeJS.Timeout | null>(null);
    const animFrameRef = useRef<number | null>(null);

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

    // Fixed pitch dimensions for no reflow
    const pitchWidth = 420;
    const pitchHeight = 280;
    const padding = 25;
    const scaleX = (pitchWidth - padding * 2) / 105;
    const scaleY = (pitchHeight - padding * 2) / 68;

    const visibleEvents = events.slice(0, currentEventIndex + 1);
    const currentEvent = events[currentEventIndex];

    if (events.length === 0) {
        return (
            <div style={{
                height: 400,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#64748b',
                background: '#f8fafc',
                borderRadius: 12
            }}>
                리플레이 데이터가 없습니다
            </div>
        );
    }

    // Easing function for smooth animation
    const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);

    return (
        <div style={{
            background: 'white',
            borderRadius: 12,
            padding: 16,
            border: '1px solid #e2e8f0',
            boxShadow: '0 2px 8px rgba(0,0,0,0.04)'
        }}>
            {/* Pitch SVG with fixed height */}
            <div style={{
                height: pitchHeight,
                position: 'relative',
                overflow: 'hidden',
                borderRadius: 8
            }}>
                <svg
                    viewBox={`0 0 ${pitchWidth} ${pitchHeight}`}
                    style={{
                        width: '100%',
                        height: '100%',
                        display: 'block'
                    }}
                >
                    {/* Gradient grass background */}
                    <defs>
                        <linearGradient id="grassGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stopColor="#4ade80" stopOpacity="0.15" />
                            <stop offset="50%" stopColor="#22c55e" stopOpacity="0.1" />
                            <stop offset="100%" stopColor="#4ade80" stopOpacity="0.15" />
                        </linearGradient>
                        <filter id="glow">
                            <feGaussianBlur stdDeviation="2" result="coloredBlur" />
                            <feMerge>
                                <feMergeNode in="coloredBlur" />
                                <feMergeNode in="SourceGraphic" />
                            </feMerge>
                        </filter>
                        <marker id="arrowBlue" markerWidth="6" markerHeight="4" refX="5" refY="2" orient="auto">
                            <polygon points="0 0, 6 2, 0 4" fill="#3b82f6" />
                        </marker>
                        <marker id="arrowRed" markerWidth="6" markerHeight="4" refX="5" refY="2" orient="auto">
                            <polygon points="0 0, 6 2, 0 4" fill="#ef4444" />
                        </marker>
                    </defs>

                    {/* Background */}
                    <rect x="0" y="0" width={pitchWidth} height={pitchHeight} fill="#fafafa" />
                    <rect x={padding} y={padding} width={pitchWidth - padding * 2} height={pitchHeight - padding * 2} fill="url(#grassGradient)" />

                    {/* Pitch lines - softer */}
                    <rect x={padding} y={padding} width={pitchWidth - padding * 2} height={pitchHeight - padding * 2} fill="none" stroke="#94a3b8" strokeWidth="1" />
                    <line x1={pitchWidth / 2} y1={padding} x2={pitchWidth / 2} y2={pitchHeight - padding} stroke="#94a3b8" strokeWidth="1" />
                    <circle cx={pitchWidth / 2} cy={pitchHeight / 2} r={32} fill="none" stroke="#94a3b8" strokeWidth="1" />

                    {/* Left penalty area */}
                    <rect x={padding} y={(pitchHeight - 90) / 2} width="50" height="90" fill="none" stroke="#94a3b8" strokeWidth="1" />
                    <rect x={padding} y={(pitchHeight - 45) / 2} width="20" height="45" fill="none" stroke="#94a3b8" strokeWidth="1" />

                    {/* Right penalty area */}
                    <rect x={pitchWidth - padding - 50} y={(pitchHeight - 90) / 2} width="50" height="90" fill="none" stroke="#94a3b8" strokeWidth="1" />
                    <rect x={pitchWidth - padding - 20} y={(pitchHeight - 45) / 2} width="20" height="45" fill="none" stroke="#94a3b8" strokeWidth="1" />

                    {/* Trail lines (past events) */}
                    {visibleEvents.slice(0, -1).map((event, i) => {
                        const x1 = padding + event.start_x * scaleX;
                        const y1 = padding + event.start_y * scaleY;
                        const x2 = padding + event.end_x * scaleX;
                        const y2 = padding + event.end_y * scaleY;
                        const hasMovement = Math.abs(event.end_x - event.start_x) > 2 || Math.abs(event.end_y - event.start_y) > 2;
                        const color = '#94a3b8';

                        return hasMovement ? (
                            <line key={`trail-${i}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth="1" strokeDasharray="4,4" opacity="0.5" />
                        ) : null;
                    })}

                    {/* Current event line with animation */}
                    {currentEvent && (() => {
                        const x1 = padding + currentEvent.start_x * scaleX;
                        const y1 = padding + currentEvent.start_y * scaleY;
                        const x2 = padding + currentEvent.end_x * scaleX;
                        const y2 = padding + currentEvent.end_y * scaleY;
                        const hasMovement = Math.abs(currentEvent.end_x - currentEvent.start_x) > 2 || Math.abs(currentEvent.end_y - currentEvent.start_y) > 2;

                        const easedProgress = easeOutCubic(animProgress);
                        const currentX2 = x1 + (x2 - x1) * easedProgress;
                        const currentY2 = y1 + (y2 - y1) * easedProgress;
                        const color = '#3b82f6';

                        return hasMovement ? (
                            <line
                                x1={x1} y1={y1}
                                x2={currentX2} y2={currentY2}
                                stroke={color}
                                strokeWidth="2.5"
                                strokeLinecap="round"
                                markerEnd="url(#arrowBlue)"
                                filter="url(#glow)"
                            />
                        ) : null;
                    })()}

                    {/* Past markers (smaller, faded) */}
                    {visibleEvents.slice(0, -1).map((event, i) => {
                        const x = padding + event.start_x * scaleX;
                        const y = padding + event.start_y * scaleY;

                        return (
                            <g key={`pastMarker-${i}`}>
                                <circle cx={x} cy={y} r={6} fill="#cbd5e1" stroke="white" strokeWidth="1.5" />
                                <text x={x} y={y + 2.5} fill="white" fontSize="7" fontWeight="600" textAnchor="middle">
                                    {i + 1}
                                </text>
                            </g>
                        );
                    })}

                    {/* Current marker (animated, highlighted) */}
                    {currentEvent && (() => {
                        const x = padding + currentEvent.start_x * scaleX;
                        const y = padding + currentEvent.start_y * scaleY;
                        const pulseScale = 1 + Math.sin(animProgress * Math.PI) * 0.15;

                        return (
                            <g style={{ transform: `translate(${x}px, ${y}px) scale(${pulseScale})`, transformOrigin: 'center', transformBox: 'fill-box' }}>
                                <circle cx={0} cy={0} r={12} fill="#3b82f6" stroke="white" strokeWidth="2" filter="url(#glow)" />
                                <text x={0} y={4} fill="white" fontSize="10" fontWeight="700" textAnchor="middle">
                                    {currentEventIndex + 1}
                                </text>
                            </g>
                        );
                    })()}

                    {/* Action label */}
                    {currentEvent && (
                        <g>
                            <rect
                                x={padding + currentEvent.start_x * scaleX - 30}
                                y={padding + currentEvent.start_y * scaleY - 32}
                                width="60" height="16" rx="4"
                                fill="rgba(15, 23, 42, 0.8)"
                            />
                            <text
                                x={padding + currentEvent.start_x * scaleX}
                                y={padding + currentEvent.start_y * scaleY - 20}
                                fill="white" fontSize="9" textAnchor="middle" fontWeight="500"
                            >
                                {currentEvent.type}
                            </text>
                        </g>
                    )}
                </svg>
            </div>

            {/* Current event info - fixed height */}
            <div style={{
                height: 44,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginTop: 12,
                padding: '0 16px',
                background: 'linear-gradient(135deg, #f1f5f9, #e2e8f0)',
                borderRadius: 8
            }}>
                <span style={{ fontWeight: 600, color: '#1e293b', fontSize: 14 }}>
                    {currentEvent?.player || '선수'}
                </span>
                <span style={{ color: '#94a3b8', margin: '0 10px', fontSize: 14 }}>·</span>
                <span style={{ color: '#3b82f6', fontWeight: 500, fontSize: 14 }}>{currentEvent?.type || '액션'}</span>
                {currentEvent?.position && currentEvent.position !== 'nan' && (
                    <>
                        <span style={{ color: '#94a3b8', margin: '0 10px', fontSize: 14 }}>·</span>
                        <span style={{ color: '#64748b', fontSize: 13 }}>{currentEvent.position}</span>
                    </>
                )}
            </div>

            {/* Controls - fixed height */}
            <div style={{
                height: 56,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 16,
                marginTop: 12
            }}>
                <button
                    onClick={handleReset}
                    style={{
                        width: 40, height: 40,
                        borderRadius: 8,
                        border: '1px solid #e2e8f0',
                        background: 'white',
                        cursor: 'pointer',
                        fontSize: 16,
                        color: '#64748b',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        transition: 'all 0.15s ease'
                    }}
                >
                    ⏮
                </button>

                <button
                    onClick={onPlayPause}
                    style={{
                        width: 52, height: 52,
                        borderRadius: 50,
                        border: 'none',
                        background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
                        color: 'white',
                        cursor: 'pointer',
                        fontSize: 20,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        boxShadow: '0 4px 12px rgba(37, 99, 235, 0.3)',
                        transition: 'transform 0.15s ease'
                    }}
                >
                    {isPlaying ? '⏸' : '▶'}
                </button>

                <div style={{ display: 'flex', gap: 4 }}>
                    {[0.5, 1, 2].map((speed) => (
                        <button
                            key={speed}
                            onClick={() => onSpeedChange(speed)}
                            style={{
                                padding: '8px 14px',
                                borderRadius: 6,
                                border: playbackSpeed === speed ? 'none' : '1px solid #e2e8f0',
                                background: playbackSpeed === speed ? 'linear-gradient(135deg, #3b82f6, #2563eb)' : 'white',
                                color: playbackSpeed === speed ? 'white' : '#64748b',
                                cursor: 'pointer',
                                fontSize: 13,
                                fontWeight: 600,
                                transition: 'all 0.15s ease'
                            }}
                        >
                            {speed}x
                        </button>
                    ))}
                </div>

                <span style={{
                    fontSize: 13,
                    color: '#64748b',
                    fontWeight: 500,
                    minWidth: 50,
                    textAlign: 'center'
                }}>
                    {currentEventIndex + 1} / {events.length}
                </span>
            </div>

            {/* Legend */}
            <div style={{
                display: 'flex',
                justifyContent: 'center',
                gap: 24,
                marginTop: 10,
                fontSize: 12,
                color: '#64748b'
            }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#3b82f6' }}></span>
                    홈 팀
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ef4444' }}></span>
                    어웨이 팀
                </span>
            </div>
        </div>
    );
}
