'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import { KeyMoment } from '@/lib/api';

const Pitch3D = dynamic(() => import('./Pitch3D'), { ssr: false });

interface KeyMomentPitchProps {
    moments: KeyMoment[];
    teamName: string;
}

const safeNum = (val: unknown, defaultVal: number): number => {
    if (val === null || val === undefined) return defaultVal;
    const num = Number(val);
    return isNaN(num) || !isFinite(num) ? defaultVal : num;
};

// CSS 3D 미니 피치
function MiniPitch3D({ moment, index }: { moment: KeyMoment; index: number }) {
    const x = safeNum(moment.position?.x, 75);
    const y = safeNum(moment.position?.y, 34);
    const suggestX = safeNum(moment.suggestion?.target_position?.x || moment.suggestion?.target_x, x + 10);
    const suggestY = safeNum(moment.suggestion?.target_position?.y || moment.suggestion?.target_y, y);

    // Scale to mini pitch (150x97)
    const scaleX = 150 / 105;
    const scaleY = 97 / 68;

    const actualPx = { x: x * scaleX, y: y * scaleY };
    const targetPx = { x: suggestX * scaleX, y: suggestY * scaleY };

    return (
        <div style={{
            perspective: '400px',
            width: 150,
            height: 97,
            cursor: 'pointer'
        }}>
            <div style={{
                width: '100%',
                height: '100%',
                position: 'relative',
                transform: 'rotateX(35deg)',
                transformStyle: 'preserve-3d',
                borderRadius: 6,
                overflow: 'hidden',
                boxShadow: '0 10px 30px rgba(0,0,0,0.25)'
            }}>
                {/* Grass with stripes */}
                <div style={{
                    position: 'absolute',
                    inset: 0,
                    background: `
                        repeating-linear-gradient(
                            90deg,
                            #2d8c3c 0px,
                            #2d8c3c 18.75px,
                            #35a045 18.75px,
                            #35a045 37.5px
                        )
                    `
                }} />

                {/* Lines */}
                <svg viewBox="0 0 150 97" style={{ position: 'absolute', inset: 0 }}>
                    {/* Outline */}
                    <rect x="2" y="2" width="146" height="93" fill="none" stroke="white" strokeWidth="1.5" />
                    {/* Center line */}
                    <line x1="75" y1="2" x2="75" y2="95" stroke="white" strokeWidth="1" />
                    {/* Center circle */}
                    <circle cx="75" cy="48.5" r="12" fill="none" stroke="white" strokeWidth="1" />
                    {/* Right penalty box */}
                    <rect x="126" y="20" width="22" height="57" fill="none" stroke="white" strokeWidth="1" />
                    {/* Right goal box */}
                    <rect x="140" y="33" width="8" height="31" fill="none" stroke="white" strokeWidth="1" />
                </svg>

                {/* Actual marker (red) */}
                <div style={{
                    position: 'absolute',
                    left: actualPx.x - 6,
                    top: actualPx.y - 6,
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    background: '#dc2626',
                    border: '2px solid white',
                    boxShadow: '0 2px 6px rgba(0,0,0,0.4)',
                    transform: 'translateZ(10px)'
                }} />

                {/* Suggest marker (green) */}
                <div style={{
                    position: 'absolute',
                    left: targetPx.x - 6,
                    top: targetPx.y - 6,
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    background: '#16a34a',
                    border: '2px solid white',
                    boxShadow: '0 2px 6px rgba(0,0,0,0.4)',
                    transform: 'translateZ(10px)'
                }} />

                {/* Arrow */}
                <svg
                    viewBox="0 0 150 97"
                    style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
                >
                    <defs>
                        <marker id={`m-arr-${index}`} markerWidth="6" markerHeight="4" refX="5" refY="2" orient="auto">
                            <polygon points="0 0, 6 2, 0 4" fill="#3b82f6" />
                        </marker>
                    </defs>
                    <line
                        x1={actualPx.x + 8}
                        y1={actualPx.y}
                        x2={targetPx.x - 8}
                        y2={targetPx.y}
                        stroke="#3b82f6"
                        strokeWidth="2"
                        markerEnd={`url(#m-arr-${index})`}
                    />
                </svg>

                {/* Click hint */}
                <div style={{
                    position: 'absolute',
                    bottom: 4,
                    right: 4,
                    fontSize: 9,
                    color: 'white',
                    background: 'rgba(0,0,0,0.5)',
                    padding: '2px 5px',
                    borderRadius: 3,
                    transform: 'translateZ(15px)'
                }}>
                    🔍 3D
                </div>
            </div>
        </div>
    );
}

// Modal component
function Modal3D({ moment, onClose }: { moment: KeyMoment; onClose: () => void }) {
    return (
        <div
            onClick={onClose}
            style={{
                position: 'fixed',
                inset: 0,
                background: 'rgba(0,0,0,0.7)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 9999,
                backdropFilter: 'blur(4px)'
            }}
        >
            <div
                onClick={(e) => e.stopPropagation()}
                style={{
                    background: 'white',
                    borderRadius: 16,
                    padding: 20,
                    boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
                    maxWidth: '90vw'
                }}
            >
                <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: 16
                }}>
                    <h3 style={{ margin: 0, fontSize: 16, color: '#1e293b' }}>
                        🏟️ {moment.player} - {moment.time_display}
                    </h3>
                    <button
                        onClick={onClose}
                        style={{
                            border: 'none',
                            background: '#f1f5f9',
                            padding: '6px 12px',
                            borderRadius: 6,
                            cursor: 'pointer',
                            fontSize: 14
                        }}
                    >
                        ✕ 닫기
                    </button>
                </div>

                <Pitch3D moment={moment} width={620} height={420} />

                <div style={{
                    display: 'flex',
                    justifyContent: 'center',
                    gap: 20,
                    marginTop: 12,
                    fontSize: 12
                }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 16, color: '#dc2626' }}>✕</span>
                        <span style={{ color: '#64748b' }}>실제 슈팅 위치</span>
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 16, fontWeight: 700, color: '#16a34a' }}>○</span>
                        <span style={{ color: '#64748b' }}>AI 제안 위치</span>
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 14, color: '#3b82f6' }}>➜</span>
                        <span style={{ color: '#64748b' }}>이동 방향</span>
                    </span>
                </div>
            </div>
        </div>
    );
}

export default function KeyMomentPitch({ moments, teamName }: KeyMomentPitchProps) {
    const [selectedMoment, setSelectedMoment] = useState<KeyMoment | null>(null);

    if (moments.length === 0) {
        return (
            <div style={{ textAlign: 'center', padding: 20, color: '#64748b', fontSize: 13 }}>
                분석할 찬스가 없습니다
            </div>
        );
    }

    return (
        <div>
            {moments.map((moment, i) => (
                <div key={i} style={{
                    marginBottom: i < moments.length - 1 ? 12 : 0,
                    border: '1px solid #e2e8f0',
                    borderRadius: 8,
                    overflow: 'hidden',
                    background: '#fff'
                }}>
                    {/* 헤더 */}
                    <div style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '8px 12px',
                        background: '#f8fafc',
                        borderBottom: '1px solid #e2e8f0'
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{
                                background: '#2563eb',
                                color: 'white',
                                padding: '2px 6px',
                                borderRadius: 4,
                                fontSize: 11,
                                fontWeight: 600
                            }}>
                                {moment.player_position || 'FW'}
                            </span>
                            <span style={{ color: '#1e293b', fontWeight: 600, fontSize: 12 }}>
                                {moment.player}
                            </span>
                        </div>
                        <span style={{ color: '#64748b', fontSize: 11 }}>
                            {moment.time_display}
                        </span>
                    </div>

                    {/* 컨텐츠 */}
                    <div style={{ display: 'flex', gap: 12, padding: 12 }}>
                        {/* 3D 미니 피치 - 클릭하면 모달 */}
                        <div onClick={() => setSelectedMoment(moment)}>
                            <MiniPitch3D moment={moment} index={i} />
                        </div>

                        {/* 분석 정보 */}
                        <div style={{ flex: 1, fontSize: 11, minWidth: 0 }}>
                            <div style={{
                                padding: '6px 8px',
                                background: '#fef2f2',
                                borderRadius: 4,
                                marginBottom: 6,
                                borderLeft: '3px solid #dc2626'
                            }}>
                                <div style={{ fontWeight: 600, color: '#dc2626', marginBottom: 2 }}>실패 원인</div>
                                <div style={{ color: '#1e293b', lineHeight: 1.3 }}>
                                    {(moment.failure_analysis?.reasons || []).slice(0, 2).join(' ')}
                                </div>
                                {(moment.failure_analysis?.xg ?? 0) > 0 && (
                                    <div style={{ color: '#64748b', marginTop: 2 }}>xG: {Math.round(moment.failure_analysis?.xg ?? 0)}%</div>
                                )}
                            </div>

                            <div style={{
                                padding: '6px 8px',
                                background: '#f0fdf4',
                                borderRadius: 4,
                                borderLeft: '3px solid #16a34a'
                            }}>
                                <div style={{ fontWeight: 600, color: '#16a34a', marginBottom: 2 }}>이렇게 했다면</div>
                                <div style={{ color: '#1e293b', lineHeight: 1.3 }}>
                                    {moment.suggestion?.description || (moment.suggestion?.reasons || []).join(' ')}
                                </div>
                                {moment.suggestion?.expected_xg && (
                                    <div style={{ color: '#16a34a', fontWeight: 600, marginTop: 2 }}>
                                        → xG: {Math.round(moment.suggestion.expected_xg)}%
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            ))}

            {/* 3D 모달 */}
            {selectedMoment && (
                <Modal3D moment={selectedMoment} onClose={() => setSelectedMoment(null)} />
            )}
        </div>
    );
}