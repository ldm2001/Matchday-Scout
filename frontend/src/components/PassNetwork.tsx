'use client';

import { useState } from 'react';

interface NetworkNode {
    id: string;
    name: string;
    position: string;
    hub_score: number;
    passes_total: number;
    avg_x?: number;
    avg_y?: number;
}

interface NetworkEdge {
    source: string;
    target: string;
    weight: number;
}

interface PassNetworkProps {
    nodes: NetworkNode[];
    edges: NetworkEdge[];
}

// 포지션별 색상
const getPositionColor = (position: string): string => {
    const pos = position.toUpperCase();
    if (pos.includes('GK')) return '#fbbf24';
    if (pos.includes('CB') || pos.includes('LB') || pos.includes('RB') || pos.includes('DF')) return '#3b82f6';
    if (pos.includes('DM') || pos.includes('CM') || pos.includes('MF')) return '#8b5cf6';
    if (pos.includes('AM') || pos.includes('WM') || pos.includes('RM') || pos.includes('LM')) return '#a78bfa';
    if (pos.includes('WF') || pos.includes('CF') || pos.includes('FW') || pos.includes('SS')) return '#ef4444';
    return '#94a3b8';
};

export default function PassNetwork({ nodes, edges }: PassNetworkProps) {
    const [hoveredNode, setHoveredNode] = useState<string | null>(null);

    const width = 650;
    const height = 420;
    const pitchPadding = 20;

    // 피치 좌표 (0-105, 0-68)를 SVG 좌표로 변환
    const toSvgX = (x: number) => {
        const normalized = Math.max(0, Math.min(105, x)) / 105;
        return pitchPadding + normalized * (width - pitchPadding * 2);
    };
    const toSvgY = (y: number) => {
        const normalized = Math.max(0, Math.min(68, y)) / 68;
        return pitchPadding + normalized * (height - pitchPadding * 2);
    };

    // 포지션별 기본 x좌표 (피치 좌표)
    const getBaseX = (position: string): number => {
        const pos = position.toUpperCase();
        if (pos.includes('GK')) return 10;
        if (pos.includes('CB')) return 25;
        if (pos.includes('LB') || pos.includes('RB')) return 30;
        if (pos.includes('DM')) return 45;
        if (pos.includes('CM')) return 55;
        if (pos.includes('AM') || pos.includes('LM') || pos.includes('RM')) return 70;
        if (pos.includes('WM') || pos.includes('WF')) return 80;
        if (pos.includes('CF') || pos.includes('FW') || pos.includes('SS')) return 90;
        return 50;
    };

    // 노드 위치 계산 (포지션 기반 + 약한 충돌 방지)
    const nodePositions = new Map<string, { x: number; y: number }>();
    const minDistance = 38;

    // 초기 위치: 포지션 기반 x, 실제 평균 y 사용
    const positions: { id: string; x: number; y: number }[] = nodes.map((node) => ({
        id: node.id,
        x: toSvgX(getBaseX(node.position)),
        y: toSvgY(node.avg_y ?? 34)
    }));

    // 약한 충돌 방지 (10회만)
    for (let iter = 0; iter < 10; iter++) {
        for (let i = 0; i < positions.length; i++) {
            for (let j = i + 1; j < positions.length; j++) {
                const dx = positions[j].x - positions[i].x;
                const dy = positions[j].y - positions[i].y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < minDistance && dist > 0) {
                    const push = (minDistance - dist) * 0.3;
                    const nx = dx / dist;
                    const ny = dy / dist;

                    positions[i].x -= nx * push;
                    positions[i].y -= ny * push;
                    positions[j].x += nx * push;
                    positions[j].y += ny * push;
                }
            }
        }
    }

    // 경계 제한
    positions.forEach(pos => {
        pos.x = Math.max(pitchPadding + 20, Math.min(width - pitchPadding - 20, pos.x));
        pos.y = Math.max(pitchPadding + 20, Math.min(height - pitchPadding - 20, pos.y));
        nodePositions.set(pos.id, { x: pos.x, y: pos.y });
    });

    // 엣지 최대 가중치
    const maxWeight = Math.max(...edges.map(e => e.weight), 1);

    // 연결된 엣지 찾기
    const getConnectedEdges = (nodeId: string) => {
        return edges.filter(e => e.source === nodeId || e.target === nodeId);
    };

    return (
        <div style={{
            background: 'white',
            borderRadius: 12,
            padding: 20,
            border: '1px solid #e2e8f0'
        }}>
            <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 12
            }}>
                <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#1e293b' }}>
                    패스 네트워크
                </h3>
                <span style={{ fontSize: 12, color: '#64748b' }}>
                    선수를 호버하면 패스 연결이 강조됩니다
                </span>
            </div>

            <svg
                width={width}
                height={height}
                style={{ display: 'block', margin: '0 auto' }}
            >
                {/* 피치 배경 */}
                <rect
                    x={pitchPadding}
                    y={pitchPadding}
                    width={width - pitchPadding * 2}
                    height={height - pitchPadding * 2}
                    fill="#2d8a3e"
                    rx={4}
                />

                {/* 피치 라인 */}
                <g stroke="rgba(255,255,255,0.5)" strokeWidth={1.5} fill="none">
                    {/* 외곽선 */}
                    <rect
                        x={pitchPadding + 5}
                        y={pitchPadding + 5}
                        width={width - pitchPadding * 2 - 10}
                        height={height - pitchPadding * 2 - 10}
                        rx={2}
                    />
                    {/* 중앙선 */}
                    <line
                        x1={width / 2}
                        y1={pitchPadding + 5}
                        x2={width / 2}
                        y2={height - pitchPadding - 5}
                    />
                    {/* 중앙원 */}
                    <circle cx={width / 2} cy={height / 2} r={40} />
                    {/* 왼쪽 페널티 박스 */}
                    <rect
                        x={pitchPadding + 5}
                        y={height / 2 - 70}
                        width={70}
                        height={140}
                    />
                    {/* 오른쪽 페널티 박스 */}
                    <rect
                        x={width - pitchPadding - 75}
                        y={height / 2 - 70}
                        width={70}
                        height={140}
                    />
                </g>

                {/* 엣지 (패스 라인) */}
                {edges.map((edge, i) => {
                    const sourcePos = nodePositions.get(edge.source);
                    const targetPos = nodePositions.get(edge.target);
                    if (!sourcePos || !targetPos) return null;

                    const isHighlighted = hoveredNode &&
                        (edge.source === hoveredNode || edge.target === hoveredNode);
                    const isDimmed = hoveredNode && !isHighlighted;

                    const strokeWidth = Math.max(1, (edge.weight / maxWeight) * 5);

                    return (
                        <line
                            key={i}
                            x1={sourcePos.x}
                            y1={sourcePos.y}
                            x2={targetPos.x}
                            y2={targetPos.y}
                            stroke={isHighlighted ? '#fbbf24' : 'rgba(255,255,255,0.3)'}
                            strokeWidth={isHighlighted ? strokeWidth + 1 : strokeWidth}
                            strokeOpacity={isDimmed ? 0.05 : isHighlighted ? 1 : 0.25}
                            style={{ transition: 'all 0.15s ease' }}
                        />
                    );
                })}

                {/* 노드 (선수) */}
                {nodes.map((node) => {
                    const pos = nodePositions.get(node.id);
                    if (!pos) return null;

                    const isHovered = hoveredNode === node.id;
                    const isConnected = hoveredNode &&
                        getConnectedEdges(hoveredNode).some(
                            e => e.source === node.id || e.target === node.id
                        );
                    const isDimmed = hoveredNode && !isHovered && !isConnected;

                    const baseRadius = 16 + node.hub_score * 10;
                    const radius = isHovered ? baseRadius + 4 : baseRadius;

                    return (
                        <g
                            key={node.id}
                            onMouseEnter={() => setHoveredNode(node.id)}
                            onMouseLeave={() => setHoveredNode(null)}
                            style={{ cursor: 'pointer' }}
                        >
                            {/* 그림자 */}
                            <circle
                                cx={pos.x + 2}
                                cy={pos.y + 2}
                                r={radius}
                                fill="rgba(0,0,0,0.2)"
                            />

                            {/* 메인 원 */}
                            <circle
                                cx={pos.x}
                                cy={pos.y}
                                r={radius}
                                fill={getPositionColor(node.position)}
                                stroke={isHovered ? '#fbbf24' : 'white'}
                                strokeWidth={isHovered ? 3 : 2}
                                opacity={isDimmed ? 0.4 : 1}
                                style={{ transition: 'all 0.15s ease' }}
                            />

                            {/* 이름 */}
                            <text
                                x={pos.x}
                                y={pos.y + 1}
                                textAnchor="middle"
                                dominantBaseline="middle"
                                fill="white"
                                fontSize={11}
                                fontWeight={700}
                                opacity={isDimmed ? 0.4 : 1}
                                style={{ pointerEvents: 'none', textShadow: '0 1px 3px rgba(0,0,0,0.8), 0 0 2px rgba(0,0,0,0.5)' }}
                            >
                                {node.name.split(' ').pop()?.slice(0, 3) || node.name.slice(0, 3)}
                            </text>

                            {/* 호버 시 상세 정보 */}
                            {isHovered && (
                                <g>
                                    <rect
                                        x={pos.x - 55}
                                        y={pos.y - radius - 45}
                                        width={110}
                                        height={38}
                                        fill="rgba(30,41,59,0.95)"
                                        rx={6}
                                    />
                                    <text
                                        x={pos.x}
                                        y={pos.y - radius - 30}
                                        textAnchor="middle"
                                        fill="white"
                                        fontSize={11}
                                        fontWeight={600}
                                    >
                                        {node.name}
                                    </text>
                                    <text
                                        x={pos.x}
                                        y={pos.y - radius - 15}
                                        textAnchor="middle"
                                        fill="#94a3b8"
                                        fontSize={10}
                                    >
                                        {node.position} • {node.passes_total} 패스
                                    </text>
                                </g>
                            )}
                        </g>
                    );
                })}
            </svg>

            {/* 범례 */}
            <div style={{
                display: 'flex',
                justifyContent: 'center',
                gap: 16,
                marginTop: 12,
                flexWrap: 'wrap'
            }}>
                {[
                    { color: '#fbbf24', label: '골키퍼' },
                    { color: '#3b82f6', label: '수비수' },
                    { color: '#8b5cf6', label: '미드필더' },
                    { color: '#ef4444', label: '공격수' },
                ].map(({ color, label }) => (
                    <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <div style={{
                            width: 12,
                            height: 12,
                            borderRadius: '50%',
                            background: color
                        }} />
                        <span style={{ fontSize: 11, color: '#64748b' }}>{label}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}
