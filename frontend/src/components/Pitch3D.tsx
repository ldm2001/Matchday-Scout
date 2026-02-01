'use client';

import { useId } from 'react';
import { KeyMoment } from '@/lib/api';
import styles from './Pitch3D.module.css';

interface Pitch3DProps {
    moment: KeyMoment;
    width?: number;
    height?: number;
}

const safeNum = (val: unknown, defaultVal: number): number => {
    if (val === null || val === undefined) return defaultVal;
    const num = Number(val);
    return isNaN(num) || !isFinite(num) ? defaultVal : num;
};

export default function Pitch3D({ moment, width = 500, height = 350 }: Pitch3DProps) {
    const svgId = useId().replace(/:/g, '');
    const clamp = (val: number, min: number, max: number) => Math.min(max, Math.max(min, val));

    const actualX = clamp(safeNum(moment.position?.x, 80), 0, 105);
    const actualY = clamp(safeNum(moment.position?.y, 34), 0, 68);
    const suggestX = clamp(
        safeNum(moment.suggestion?.target_position?.x || moment.suggestion?.target_x, actualX + 8),
        0,
        105
    );
    const suggestY = clamp(
        safeNum(moment.suggestion?.target_position?.y || moment.suggestion?.target_y, actualY),
        0,
        68
    );
    const dx = suggestX - actualX;
    const dy = suggestY - actualY;
    const moveDistance = Math.hypot(dx, dy);
    const dirScale = moveDistance > 0.01 ? 1 / moveDistance : 0;
    const dirX = moveDistance > 0.01 ? dx * dirScale : 1;
    const dirY = moveDistance > 0.01 ? dy * dirScale : 0;
    const perpX = -dirY;
    const perpY = dirX;
    const midX = (actualX + suggestX) / 2 + perpX * 1.4;
    const midY = (actualY + suggestY) / 2 + perpY * 1.4;
    const pathPad = 2.2;
    const minLine = 8;
    const drawLen = moveDistance > 0.01 ? Math.max(moveDistance, minLine) : minLine;
    const lineEndX = moveDistance >= minLine ? suggestX : clamp(actualX + dirX * drawLen, 0, 105);
    const lineEndY = moveDistance >= minLine ? suggestY : clamp(actualY + dirY * drawLen, 0, 68);
    const startX = clamp(actualX + dirX * pathPad, 0, 105);
    const startY = clamp(actualY + dirY * pathPad, 0, 68);
    const endX = clamp(lineEndX - dirX * pathPad, 0, 105);
    const endY = clamp(lineEndY - dirY * pathPad, 0, 68);
    const labelClampX = (val: number) => clamp(val, 4, 101);
    const labelClampY = (val: number) => clamp(val, 4, 64);
    const labelOffset = 3.2;
    const actualLabelX = labelClampX(actualX - dirX * 2.6 + perpX * labelOffset);
    const actualLabelY = labelClampY(actualY - dirY * 2.6 + perpY * labelOffset);
    const aiLabelX = labelClampX(suggestX + dirX * 2.6 + perpX * labelOffset);
    const aiLabelY = labelClampY(suggestY + dirY * 2.6 + perpY * labelOffset);
    const anchorFromX = (x: number, fallback: 'start' | 'end') => {
        if (x < 18) return 'start';
        if (x > 90) return 'end';
        return fallback;
    };
    const actualAnchor = anchorFromX(actualLabelX, dirX >= 0 ? 'end' : 'start');
    const aiAnchor = anchorFromX(aiLabelX, dirX >= 0 ? 'start' : 'end');

    const penaltyBox = { width: 16.5, height: 40.32 };
    const goalBox = { width: 5.5, height: 18.32 };
    const boxY = (68 - penaltyBox.height) / 2;
    const goalBoxY = (68 - goalBox.height) / 2;

    return (
        <div className={styles.pitchFrame} style={{ width, height }}>
            <svg
                className={styles.pitchSvg}
                viewBox="0 0 105 68"
                preserveAspectRatio="xMidYMid meet"
            >
                <defs>
                    <linearGradient id={`grass-${svgId}`} x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0%" stopColor="#eef2f7" />
                        <stop offset="100%" stopColor="#e2e8f0" />
                    </linearGradient>
                    <pattern id={`grid-${svgId}`} width="10" height="10" patternUnits="userSpaceOnUse">
                        <path d="M 10 0 L 0 0 0 10" className={styles.pitchGrid} />
                    </pattern>
                    <marker
                        id={`arrow-${svgId}`}
                        markerWidth="6"
                        markerHeight="6"
                        refX="5.2"
                        refY="3"
                        orient="auto"
                        markerUnits="userSpaceOnUse"
                    >
                        <path d="M0,0 L6,3 L0,6 Z" className={styles.pathArrow} />
                    </marker>
                </defs>

                <rect x="0" y="0" width="105" height="68" fill={`url(#grass-${svgId})`} />
                <rect x="0" y="0" width="105" height="68" fill={`url(#grid-${svgId})`} />

                <rect x="0.5" y="0.5" width="104" height="67" className={styles.pitchLine} />
                <line x1="52.5" y1="0.5" x2="52.5" y2="67.5" className={styles.pitchLine} />
                <circle cx="52.5" cy="34" r="9.15" className={styles.pitchLine} />
                <circle cx="52.5" cy="34" r="0.7" className={styles.pitchSpot} />

                <rect x="0" y={boxY} width={penaltyBox.width} height={penaltyBox.height} className={styles.pitchLine} />
                <rect x={105 - penaltyBox.width} y={boxY} width={penaltyBox.width} height={penaltyBox.height} className={styles.pitchLine} />
                <rect x="0" y={goalBoxY} width={goalBox.width} height={goalBox.height} className={styles.pitchLine} />
                <rect x={105 - goalBox.width} y={goalBoxY} width={goalBox.width} height={goalBox.height} className={styles.pitchLine} />
                <circle cx="11" cy="34" r="0.6" className={styles.pitchSpot} />
                <circle cx="94" cy="34" r="0.6" className={styles.pitchSpot} />

                {moveDistance > 0.2 && (
                    <line
                        x1={startX}
                        y1={startY}
                        x2={endX}
                        y2={endY}
                        className={styles.pathLine}
                        markerEnd={`url(#arrow-${svgId})`}
                    />
                )}

                <circle cx={actualX} cy={actualY} r="1.8" className={styles.markerActual} />
                <circle cx={suggestX} cy={suggestY} r="2.6" className={styles.markerTarget} />
                <circle cx={suggestX} cy={suggestY} r="0.7" className={styles.markerTargetCore} />

                <text x={actualLabelX} y={actualLabelY} textAnchor={actualAnchor} className={styles.markerLabel}>
                    실제
                </text>
                <text x={aiLabelX} y={aiLabelY} textAnchor={aiAnchor} className={styles.markerLabelAi}>
                    AI
                </text>

                {moveDistance > 2 && (
                    <text x={midX} y={labelClampY(midY - 1)} textAnchor="middle" className={styles.pathLabel}>
                        {Number.isFinite(moveDistance) ? `${moveDistance.toFixed(1)}m` : ''}
                    </text>
                )}
            </svg>
        </div>
    );
}
