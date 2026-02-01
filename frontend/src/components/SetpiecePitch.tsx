// 세트피스 피치 시각화 컴포넌트 - 코너킥/프리킥 경로와 타겟존 표시
'use client';

// 세트피스 루틴 데이터 타입
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

// 안전한 숫자 변환 (null/undefined/NaN 처리)
const safeNum = (val: unknown, defaultVal: number): number => {
    if (val === null || val === undefined) return defaultVal;
    const num = Number(val);
    return isNaN(num) || !isFinite(num) ? defaultVal : num;
};

export default function SetpiecePitch({ routine }: SetpiecePitchProps) {
    const pitchWidth = 720;
    const pitchHeight = 460;
    const padding = 30;
    const scaleX = (pitchWidth - padding * 2) / 105;
    const scaleY = (pitchHeight - padding * 2) / 68;

    const isCorner = routine.type.includes('Corner');

    // 코너킥/프리킥 시작 위치 (오른쪽 공격 방향 기준)
    let startX: number, startY: number;

    if (isCorner) {
        // 코너킥: 오른쪽 코너 (안쪽으로 약간 들어옴)
        startX = 100;
        startY = routine.avg_target_y > 34 ? 5 : 63;
    } else {
        // 프리킥: 오른쪽 영역 근처
        startX = Math.min(safeNum(routine.avg_target_x, 70), 90);
        startY = safeNum(routine.avg_target_y, 34);
    }

    // 타겟 위치 (좌표 변환 필요할 수 있음)
    let targetX = safeNum(routine.avg_target_x, 90);
    let targetY = safeNum(routine.avg_target_y, 34);

    // 좌표가 0-105 범위 밖이면 보정
    if (targetX < 50) {
        targetX = 105 - targetX; // 좌표 반전
    }
    if (targetY > 68) targetY = 68;
    if (targetY < 0) targetY = 0;

    // 피치 좌표로 변환
    const sx = padding + startX * scaleX;
    const sy = padding + startY * scaleY;
    const tx = padding + targetX * scaleX;
    const ty = padding + targetY * scaleY;

    // 곡선 계산 (인스윙/아웃스윙)
    const isInswing = routine.swing_type === 'inswing';
    const curveOffset = isInswing ? -30 : 30;
    const midX = (sx + tx) / 2;
    const midY = (sy + ty) / 2 + curveOffset;

    return (
        <svg
            viewBox={`0 0 ${pitchWidth} ${pitchHeight}`}
            style={{
                width: pitchWidth,
                height: pitchHeight,
                maxWidth: '100%',
                display: 'block',
                border: '1px solid #e2e8f0',
                borderRadius: 6,
                marginBottom: 10
            }}
        >
            {/* Background */}
            <rect x="0" y="0" width={pitchWidth} height={pitchHeight} fill="#f5f5f0" />

            {/* Pitch outline */}
            <rect
                x={padding}
                y={padding}
                width={pitchWidth - padding * 2}
                height={pitchHeight - padding * 2}
                fill="none"
                stroke="#333"
                strokeWidth="1.5"
            />

            {/* Center line */}
            <line
                x1={pitchWidth / 2}
                y1={padding}
                x2={pitchWidth / 2}
                y2={pitchHeight - padding}
                stroke="#333"
                strokeWidth="1.5"
            />

            {/* Center circle */}
            <circle
                cx={pitchWidth / 2}
                cy={pitchHeight / 2}
                r={22}
                fill="none"
                stroke="#333"
                strokeWidth="1.5"
            />

            {/* Right penalty box */}
            <rect
                x={pitchWidth - padding - 38}
                y={(pitchHeight - 68) / 2}
                width="38"
                height="68"
                fill="none"
                stroke="#333"
                strokeWidth="1.5"
            />

            {/* Right goal box */}
            <rect
                x={pitchWidth - padding - 15}
                y={(pitchHeight - 30) / 2}
                width="15"
                height="30"
                fill="none"
                stroke="#333"
                strokeWidth="1.5"
            />

            {/* Left penalty box */}
            <rect
                x={padding}
                y={(pitchHeight - 68) / 2}
                width="38"
                height="68"
                fill="none"
                stroke="#333"
                strokeWidth="1.5"
            />

            {/* Arrow marker */}
            <defs>
                <marker id="setpiece-arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
                    <polygon points="0 0, 8 3, 0 6" fill={isCorner ? "#2563eb" : "#16a34a"} />
                </marker>
            </defs>

            {/* Curved path from start to target */}
            <path
                d={`M ${sx} ${sy} Q ${midX} ${midY} ${tx} ${ty}`}
                stroke={isCorner ? "#2563eb" : "#16a34a"}
                strokeWidth="2.5"
                strokeDasharray="6,3"
                fill="none"
                markerEnd="url(#setpiece-arrow)"
            />

            {/* Start position (ball icon) */}
            <circle cx={sx} cy={sy} r="8" fill="#fff" stroke="#333" strokeWidth="1.5" />
            <text x={sx} y={sy + 4} fill="#333" fontSize="10" fontWeight="bold" textAnchor="middle">⚽</text>

            {/* Target zone (highlighted area) */}
            <ellipse
                cx={tx}
                cy={ty}
                rx="20"
                ry="15"
                fill={isCorner ? "rgba(37, 99, 235, 0.2)" : "rgba(22, 163, 74, 0.2)"}
                stroke={isCorner ? "#2563eb" : "#16a34a"}
                strokeWidth="1.5"
                strokeDasharray="4,2"
            />

            {/* Target center */}
            <circle
                cx={tx}
                cy={ty}
                r="5"
                fill={isCorner ? "#2563eb" : "#16a34a"}
            />

            {/* Labels */}
            <text x={sx} y={sy + 18} fill="#64748b" fontSize="9" textAnchor="middle">
                {isCorner ? '코너' : '프리킥'}
            </text>
            <text x={tx} y={ty + 25} fill="#64748b" fontSize="9" textAnchor="middle">
                타겟존
            </text>
        </svg>
    );
}
