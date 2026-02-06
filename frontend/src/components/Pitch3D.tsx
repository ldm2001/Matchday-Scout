// 3D 피치 시각화 컴포넌트 - 키 모멘트의 실제/AI 추천 위치 표시
'use client';

import { useId } from 'react';
import { KeyMoment } from '@/lib/api';
import styles from './Pitch3D.module.css';

interface Pitch3DProps {
    moment: KeyMoment;
    width?: number;
    height?: number;
}

// 안전한 숫자 변환 (null/undefined/NaN 처리)
const safeNum = (val: unknown, defaultVal: number): number => {
    if (val === null || val === undefined) return defaultVal;
    const num = Number(val);
    return isNaN(num) || !isFinite(num) ? defaultVal : num;
};

// SVG 피치에 실제 위치, AI 추천 위치, 이동 경로를 표시
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
    const hasMovement = moveDistance > 0.35;
    const dirScale = hasMovement ? 1 / moveDistance : 0;
    const dirX = hasMovement ? dx * dirScale : 1;
    const dirY = hasMovement ? dy * dirScale : 0;
    const perpX = -dirY;
    const perpY = dirX;
    const pathPad = hasMovement ? clamp(moveDistance * 0.08, 0.28, 0.95) : 0;
    const startX = hasMovement ? clamp(actualX + dirX * pathPad, 0, 105) : actualX;
    const startY = hasMovement ? clamp(actualY + dirY * pathPad, 0, 68) : actualY;
    const endX = hasMovement ? clamp(suggestX - dirX * pathPad, 0, 105) : suggestX;
    const endY = hasMovement ? clamp(suggestY - dirY * pathPad, 0, 68) : suggestY;
    const nearTop = Math.min(actualY, suggestY) < 11;
    const nearBottom = Math.max(actualY, suggestY) > 57;
    const curveDirection = nearTop ? 1 : nearBottom ? -1 : (dy >= 0 ? -1 : 1);
    const baseCurve = clamp(moveDistance * 0.14, 0.7, 3.2);
    const curveStrength = hasMovement ? (moveDistance < 2.2 ? baseCurve * 0.55 : baseCurve) : 0;
    const ctrlX = clamp((startX + endX) / 2 + perpX * curveStrength * curveDirection, 4, 101);
    const ctrlY = clamp((startY + endY) / 2 + perpY * curveStrength * curveDirection, 4, 64);
    const movementPath = `M ${startX} ${startY} Q ${ctrlX} ${ctrlY} ${endX} ${endY}`;
    const showArrow = moveDistance > 2.3;

    const labelClampX = (val: number) => clamp(val, 6, 99);
    const labelClampY = (val: number) => clamp(val, 6, 62);
    const labelOffset = moveDistance < 7 ? 4.8 : 4.1;
    let actualLabelX = actualX - dirX * 2.3 - perpX * labelOffset;
    let actualLabelY = actualY - dirY * 2.3 - perpY * labelOffset;
    let aiLabelX = suggestX + dirX * 2.3 + perpX * labelOffset;
    let aiLabelY = suggestY + dirY * 2.3 + perpY * labelOffset;

    if (moveDistance < 5.4) {
        actualLabelX -= perpX * 1.4 + dirX * 0.8;
        actualLabelY -= perpY * 1.4 + dirY * 0.8;
        aiLabelX += perpX * 1.4 + dirX * 0.8;
        aiLabelY += perpY * 1.4 + dirY * 0.8;
    }

    if (!hasMovement) {
        actualLabelX = actualX - 4.2;
        actualLabelY = actualY - 4.8;
        aiLabelX = suggestX + 4.2;
        aiLabelY = suggestY - 4.8;
    }

    actualLabelX = labelClampX(actualLabelX);
    actualLabelY = labelClampY(actualLabelY);
    aiLabelX = labelClampX(aiLabelX);
    aiLabelY = labelClampY(aiLabelY);

    const projectPoint = (fromX: number, fromY: number, toX: number, toY: number, dist: number) => {
        const vx = toX - fromX;
        const vy = toY - fromY;
        const len = Math.hypot(vx, vy);
        if (!Number.isFinite(len) || len < 0.001) return { x: fromX, y: fromY };
        return {
            x: fromX + (vx / len) * dist,
            y: fromY + (vy / len) * dist,
        };
    };
    const actualLinkStart = projectPoint(actualX, actualY, actualLabelX, actualLabelY, 2.25);
    const actualLinkEnd = projectPoint(actualLabelX, actualLabelY, actualX, actualY, 2.6);
    const aiLinkStart = projectPoint(suggestX, suggestY, aiLabelX, aiLabelY, 2.9);
    const aiLinkEnd = projectPoint(aiLabelX, aiLabelY, suggestX, suggestY, 2.3);

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
                        <stop offset="0%" stopColor="#f7fbff" />
                        <stop offset="100%" stopColor="#e8f1fb" />
                    </linearGradient>
                    <pattern id={`stripe-${svgId}`} width="12" height="68" patternUnits="userSpaceOnUse">
                        <rect x="0" y="0" width="6" height="68" className={styles.pitchStripe} />
                    </pattern>
                    <pattern id={`grid-${svgId}`} width="10" height="10" patternUnits="userSpaceOnUse">
                        <path d="M 10 0 L 0 0 0 10" className={styles.pitchGrid} />
                    </pattern>
                    <linearGradient
                        id={`path-gradient-${svgId}`}
                        x1={startX}
                        y1={startY}
                        x2={endX}
                        y2={endY}
                        gradientUnits="userSpaceOnUse"
                    >
                        <stop offset="0%" stopColor="#f97316" />
                        <stop offset="100%" stopColor="#f59e0b" />
                    </linearGradient>
                    <filter id={`path-glow-${svgId}`} x="-30%" y="-30%" width="160%" height="160%">
                        <feDropShadow dx="0" dy="0.2" stdDeviation="0.52" floodColor="#f59e0b" floodOpacity="0.32" />
                    </filter>
                    <marker
                        id={`arrow-${svgId}`}
                        markerWidth="6.6"
                        markerHeight="6.6"
                        refX="6.05"
                        refY="3.3"
                        orient="auto"
                        markerUnits="userSpaceOnUse"
                    >
                        <path d="M0,0 L6.6,3.3 L0,6.6 L1.15,3.3 Z" className={styles.pathArrow} />
                    </marker>
                </defs>

                <rect x="0" y="0" width="105" height="68" fill={`url(#grass-${svgId})`} />
                <rect x="0" y="0" width="105" height="68" fill={`url(#stripe-${svgId})`} />
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

                {hasMovement && (
                    <>
                        <path d={movementPath} className={styles.pathUnderlay} />
                        <path
                            d={movementPath}
                            className={styles.pathLine}
                            style={{ stroke: `url(#path-gradient-${svgId})` }}
                            filter={`url(#path-glow-${svgId})`}
                            markerEnd={showArrow ? `url(#arrow-${svgId})` : undefined}
                        />
                    </>
                )}

                <line x1={actualLinkStart.x} y1={actualLinkStart.y} x2={actualLinkEnd.x} y2={actualLinkEnd.y} className={styles.markerLinkActual} />
                <line x1={aiLinkStart.x} y1={aiLinkStart.y} x2={aiLinkEnd.x} y2={aiLinkEnd.y} className={styles.markerLinkAi} />

                <circle cx={actualX} cy={actualY} r="3.35" className={styles.markerActualHalo} />
                <circle cx={actualX} cy={actualY} r="2.15" className={styles.markerActualRing} />
                <circle cx={actualX} cy={actualY} r="1.55" className={styles.markerActual} />
                <circle cx={actualX} cy={actualY} r="0.45" className={styles.markerActualCore} />

                <circle cx={suggestX} cy={suggestY} r="4.7" className={styles.markerTargetOrbit} />
                <circle cx={suggestX} cy={suggestY} r="3.95" className={styles.markerTargetAura} />
                <circle cx={suggestX} cy={suggestY} r="2.65" className={styles.markerTarget} />
                <circle cx={suggestX} cy={suggestY} r="1.25" className={styles.markerTargetInner} />
                <circle cx={suggestX} cy={suggestY} r="0.55" className={styles.markerTargetCore} />

                <g transform={`translate(${actualLabelX} ${actualLabelY})`}>
                    <rect x="-4.7" y="-2.1" width="9.4" height="4.2" rx="2.1" className={styles.markerLabelActualBg} />
                    <text x="0" y="0.05" className={styles.markerLabelActual}>
                        실제
                    </text>
                </g>
                <g transform={`translate(${aiLabelX} ${aiLabelY})`}>
                    <rect x="-3.6" y="-2.1" width="7.2" height="4.2" rx="2.1" className={styles.markerLabelAiBg} />
                    <text x="0" y="0.05" className={styles.markerLabelAi}>
                        AI
                    </text>
                </g>
            </svg>
        </div>
    );
}
