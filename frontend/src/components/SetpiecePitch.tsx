// 세트피스 피치 시각화 컴포넌트 - K리그 문자중계 스타일
'use client';

import { useId } from 'react';
import styles from './SetpiecePitch.module.css';

interface SetpieceRoutine {
    type: string;
    cluster_id: number;
    frequency: number;
    shot_rate: number;
    primary_zone: string;
    swing_type: string;
    avg_target_x: number;
    avg_target_y: number;
    defense_suggestion: string;
}

interface SetpiecePitchProps {
    routine: SetpieceRoutine;
}

const safeNum = (val: unknown, defaultVal: number): number => {
    if (val === null || val === undefined) return defaultVal;
    const num = Number(val);
    return isNaN(num) || !isFinite(num) ? defaultVal : num;
};

const clamp = (v: number, min: number, max: number) => Math.min(max, Math.max(min, v));

export default function SetpiecePitch({ routine }: SetpiecePitchProps) {
    const uid = useId().replace(/:/g, '');
    // 실제 축구장 비율 (105m x 68m)
    const W = 105;
    const H = 68;

    const isCorner = routine.type.includes('Corner');
    const isInswing = routine.swing_type === 'inswing';

    // 타겟 좌표 보정 (좌표가 좌측에 있다면 반전)
    let rawTargetX = safeNum(routine.avg_target_x, 95);
    const rawTargetY = safeNum(routine.avg_target_y, 34);
    if (rawTargetX < 50) rawTargetX = W - rawTargetX;
    const targetX = clamp(rawTargetX, 70, W - 1.5);
    const targetY = clamp(rawTargetY, 12, H - 12);

    // 킥 시작 위치 결정
    let startX: number, startY: number;
    if (isCorner) {
        startX = W;
        startY = targetY > 34 ? 0 : H;
    } else {
        // 프리킥: 박스 외곽으로 후퇴된 위치
        const offset = 18;
        startX = clamp(targetX - offset, 60, W - 18);
        startY = clamp(targetY + (targetY > 34 ? 4 : -4), 8, H - 8);
    }

    // 곡선 제어점 (인스윙/아웃스윙)
    const dx = targetX - startX;
    const dy = targetY - startY;
    const dist = Math.hypot(dx, dy) || 1;
    const ux = dx / dist;
    const uy = dy / dist;
    // 수직 방향
    const px = -uy;
    const py = ux;
    // 인스윙은 안쪽(골 방향), 아웃스윙은 바깥쪽으로 휨
    const swingDir = isInswing ? -1 : 1;
    const curveAmount = clamp(dist * 0.18, 3, 8);
    const midX = (startX + targetX) / 2 + px * curveAmount * swingDir;
    const midY = (startY + targetY) / 2 + py * curveAmount * swingDir;

    // 영향 콘 구역 (킥지점에서 타겟존 방향으로 부채꼴)
    const coneSpread = clamp(dist * 0.22, 6, 14);
    const coneEndX = startX + ux * dist;
    const coneEndY = startY + uy * dist;
    const coneA = `${coneEndX + px * coneSpread},${coneEndY + py * coneSpread}`;
    const coneB = `${coneEndX - px * coneSpread},${coneEndY - py * coneSpread}`;

    // 타겟존 라벨 한글화
    const zoneMap: Record<string, string> = {
        near_post: '니어 포스트',
        far_post: '파 포스트',
        central: '중앙',
        edge_of_box: '박스 외곽',
        penalty_spot: '페널티 스팟',
        six_yard: '6야드 박스',
    };
    const zoneLabel = zoneMap[routine.primary_zone] || routine.primary_zone;

    // 모션 경로 (볼 애니메이션용)
    const motionPath = `M ${startX} ${startY} Q ${midX} ${midY} ${targetX} ${targetY}`;

    // 색상 토큰
    const accent = isCorner ? '#fbbf24' : '#22d3ee';
    const accentRGB = isCorner ? '251, 191, 36' : '34, 211, 238';

    return (
        <div className={styles.pitchFrame}>
            {/* 정보 오버레이 (피치 위쪽) */}
            <div className={styles.headerBar}>
                <div className={styles.timePill}>
                    {isCorner ? '코너킥' : '프리킥'} · {isInswing ? '인스윙' : '아웃스윙'}
                </div>
                <div className={styles.kickerCard}>
                    <span className={styles.kickerIcon}>⚽</span>
                    <span className={styles.kickerName}>
                        {zoneLabel} 타겟 · 슛전환 {(routine.shot_rate * 100).toFixed(0)}%
                    </span>
                </div>
            </div>

            <svg
                viewBox={`-3 -3 ${W + 6} ${H + 6}`}
                className={styles.pitchSvg}
                preserveAspectRatio="xMidYMid meet"
                style={{ '--kg-accent': accent, '--kg-accent-rgb': accentRGB } as React.CSSProperties}
            >
                <defs>
                    {/* 잔디 그라디언트 */}
                    <linearGradient id={`grass-${uid}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#4a8b3a" />
                        <stop offset="55%" stopColor="#3d7a2e" />
                        <stop offset="100%" stopColor="#2f6024" />
                    </linearGradient>

                    {/* 잔디 줄무늬 */}
                    <pattern id={`stripe-${uid}`} width="7" height="68" patternUnits="userSpaceOnUse">
                        <rect width="3.5" height="68" fill="rgba(255,255,255,0.045)" />
                        <rect x="3.5" width="3.5" height="68" fill="rgba(0,0,0,0.04)" />
                    </pattern>

                    {/* 콘 영향 구역 그라디언트 */}
                    <radialGradient id={`cone-${uid}`} cx="0" cy="0.5" r="1.1" fx="0" fy="0.5">
                        <stop offset="0%" stopColor="rgba(255,255,255,0.55)" />
                        <stop offset="55%" stopColor="rgba(255,255,255,0.18)" />
                        <stop offset="100%" stopColor="rgba(255,255,255,0)" />
                    </radialGradient>

                    {/* 패스 글로우 */}
                    <filter id={`glow-${uid}`} x="-30%" y="-30%" width="160%" height="160%">
                        <feGaussianBlur stdDeviation="0.55" result="b" />
                        <feMerge>
                            <feMergeNode in="b" />
                            <feMergeNode in="SourceGraphic" />
                        </feMerge>
                    </filter>

                    {/* 화살표 마커 */}
                    <marker
                        id={`arrow-${uid}`}
                        markerWidth="6"
                        markerHeight="6"
                        refX="5"
                        refY="3"
                        orient="auto"
                        markerUnits="userSpaceOnUse"
                    >
                        <path d="M0,0 L6,3 L0,6 L1.4,3 Z" fill={accent} />
                    </marker>

                    {/* 모션 경로 (보이지 않음 - 볼 애니메이션용) */}
                    <path id={`motion-${uid}`} d={motionPath} fill="none" stroke="none" />
                </defs>

                {/* 잔디 배경 */}
                <rect x="-3" y="-3" width={W + 6} height={H + 6} fill={`url(#grass-${uid})`} />
                <rect x="0" y="0" width={W} height={H} fill={`url(#stripe-${uid})`} />

                {/* 외곽 그림자 */}
                <rect x="0" y="0" width={W} height={H} fill="none" stroke="rgba(0,0,0,0.18)" strokeWidth="0.4" />

                {/* 필드 라인 */}
                <rect x="0" y="0" width={W} height={H} className={styles.line} />
                <line x1={W / 2} y1="0" x2={W / 2} y2={H} className={styles.line} />
                <circle cx={W / 2} cy={H / 2} r="9.15" className={styles.line} />
                <circle cx={W / 2} cy={H / 2} r="0.45" className={styles.spot} />

                {/* 페널티 박스 */}
                <rect x="0" y={(H - 40.32) / 2} width="16.5" height="40.32" className={styles.line} />
                <rect x={W - 16.5} y={(H - 40.32) / 2} width="16.5" height="40.32" className={styles.line} />

                {/* 골 박스 */}
                <rect x="0" y={(H - 18.32) / 2} width="5.5" height="18.32" className={styles.line} />
                <rect x={W - 5.5} y={(H - 18.32) / 2} width="5.5" height="18.32" className={styles.line} />

                {/* 페널티 스팟 */}
                <circle cx="11" cy={H / 2} r="0.45" className={styles.spot} />
                <circle cx={W - 11} cy={H / 2} r="0.45" className={styles.spot} />

                {/* 페널티 아크 */}
                <path d={`M 16.5 ${H / 2 - 7.31} A 9.15 9.15 0 0 1 16.5 ${H / 2 + 7.31}`} className={styles.line} fill="none" />
                <path d={`M ${W - 16.5} ${H / 2 - 7.31} A 9.15 9.15 0 0 0 ${W - 16.5} ${H / 2 + 7.31}`} className={styles.line} fill="none" />

                {/* 코너 아크 */}
                <path d="M 0 1 A 1 1 0 0 1 1 0" className={styles.line} fill="none" />
                <path d={`M ${W - 1} 0 A 1 1 0 0 1 ${W} 1`} className={styles.line} fill="none" />
                <path d={`M 0 ${H - 1} A 1 1 0 0 0 1 ${H}`} className={styles.line} fill="none" />
                <path d={`M ${W} ${H - 1} A 1 1 0 0 0 ${W - 1} ${H}`} className={styles.line} fill="none" />

                {/* 코너 빨간 점 */}
                <circle cx="0" cy="0" r="0.85" className={styles.cornerDot} />
                <circle cx={W} cy="0" r="0.85" className={styles.cornerDot} />
                <circle cx="0" cy={H} r="0.85" className={styles.cornerDot} />
                <circle cx={W} cy={H} r="0.85" className={styles.cornerDot} />

                {/* 영향 콘 구역 */}
                <polygon
                    points={`${startX},${startY} ${coneA} ${coneB}`}
                    fill={`url(#cone-${uid})`}
                    className={styles.coneZone}
                />

                {/* 곡선 패스 (밑면 + 위) */}
                <path d={motionPath} className={styles.pathBase} fill="none" />
                <path
                    d={motionPath}
                    className={styles.pathLine}
                    fill="none"
                    markerEnd={`url(#arrow-${uid})`}
                    filter={`url(#glow-${uid})`}
                />

                {/* 타겟존 (펄스 링) */}
                <circle cx={targetX} cy={targetY} r="6" className={styles.targetOuter} />
                <ellipse cx={targetX} cy={targetY} rx="4.5" ry="3.3" className={styles.targetZone} />
                <circle cx={targetX} cy={targetY} r="1.1" className={styles.targetCenter} />

                {/* 킥지점 (펄스) */}
                <circle cx={startX} cy={startY} r="3.6" className={styles.kickPulse} />
                <circle cx={startX} cy={startY} r="1.9" className={styles.kickRing} />
                <circle cx={startX} cy={startY} r="0.9" className={styles.kickDot} />

                {/* 움직이는 볼 */}
                <circle r="0.95" className={styles.movingBall}>
                    <animateMotion dur="2.6s" repeatCount="indefinite" rotate="auto">
                        <mpath xlinkHref={`#motion-${uid}`} />
                    </animateMotion>
                </circle>

                {/* 타겟존 라벨 */}
                <g transform={`translate(${targetX} ${targetY + 8.5})`}>
                    <rect x="-7.5" y="-1.95" width="15" height="3.9" rx="1.95" className={styles.zoneLabelBg} />
                    <text x="0" y="0.6" className={styles.zoneLabelText}>
                        {zoneLabel}
                    </text>
                </g>
            </svg>

            {/* 하단 통계 바 */}
            <div className={styles.footerBar}>
                <div className={styles.statBlock}>
                    <span className={styles.statValue}>{routine.frequency}</span>
                    <span className={styles.statLabel}>발생</span>
                </div>
                <div className={styles.statDivider} />
                <div className={styles.statBlock}>
                    <span className={styles.statValue}>{(routine.shot_rate * 100).toFixed(0)}%</span>
                    <span className={styles.statLabel}>슈팅 전환</span>
                </div>
                <div className={styles.statDivider} />
                <div className={styles.statBlock}>
                    <span className={styles.statValue}>{isInswing ? '인' : '아웃'}</span>
                    <span className={styles.statLabel}>스윙</span>
                </div>
            </div>
        </div>
    );
}
