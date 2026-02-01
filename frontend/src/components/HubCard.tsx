// 빌드업 허브 선수 정보 카드 컴포넌트
'use client';

import { Hub } from '@/types';

interface HubCardProps {
    hub: Hub;
    onSimulate?: () => void;
}

// 허브 영향도에 따른 색상/라벨 표시 및 압박 시뮬레이션 버튼 제공
export default function HubCard({ hub, onSimulate }: HubCardProps) {
    // 영향도 점수에 따른 색상 클래스 반환
    const getImpactColor = (score: number) => {
        if (score >= 70) return 'text-red-400 bg-red-500/10';
        if (score >= 40) return 'text-yellow-400 bg-yellow-500/10';
        return 'text-blue-400 bg-blue-500/10';
    };

    const getImpactLabel = (score: number) => {
        if (score >= 70) return '최우선 타겟';
        if (score >= 40) return '효과적 타겟';
        return '보조 타겟';
    };

    return (
        <div className="card card-hover animate-fade-in">
            <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center text-white font-bold">
                        {hub.position}
                    </div>
                    <div>
                        <h3 className="font-semibold text-white text-lg">{hub.player_name}</h3>
                        <p className="text-sm text-slate-400">{hub.main_position} • 허브 점수 {(hub.hub_score * 100).toFixed(0)}</p>
                    </div>
                </div>
                <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getImpactColor(hub.disruption_impact.impact_score)}`}>
                    {getImpactLabel(hub.disruption_impact.impact_score)}
                </span>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="p-3 bg-slate-800/50 rounded-lg">
                    <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-slate-400">패스 수신</span>
                        <span className="text-lg font-bold text-green-400">{hub.passes_received}</span>
                    </div>
                    <div className="w-full bg-slate-700 rounded-full h-1.5">
                        <div
                            className="bg-green-500 h-1.5 rounded-full"
                            style={{ width: `${Math.min(100, hub.passes_received / 2)}%` }}
                        />
                    </div>
                </div>
                <div className="p-3 bg-slate-800/50 rounded-lg">
                    <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-slate-400">패스 시도</span>
                        <span className="text-lg font-bold text-blue-400">{hub.passes_made}</span>
                    </div>
                    <div className="w-full bg-slate-700 rounded-full h-1.5">
                        <div
                            className="bg-blue-500 h-1.5 rounded-full"
                            style={{ width: `${Math.min(100, hub.passes_made / 2)}%` }}
                        />
                    </div>
                </div>
            </div>

            <div className="mb-4">
                <p className="text-xs text-slate-400 mb-2">주요 연결</p>
                <div className="space-y-2">
                    {hub.key_connections.slice(0, 4).map((conn, i) => (
                        <div key={i} className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-2">
                                <span className={`w-2 h-2 rounded-full ${conn.type === 'passes_to' ? 'bg-blue-500' : 'bg-green-500'}`} />
                                <span className="text-white">{conn.player_name}</span>
                                <span className="text-slate-500 text-xs">({conn.position || '?'})</span>
                            </div>
                            <span className="text-slate-400">{conn.count}회</span>
                        </div>
                    ))}
                </div>
            </div>

            <div className="p-3 bg-slate-800 rounded-lg mb-4">
                <p className="text-sm text-slate-300">{hub.disruption_impact.description}</p>
            </div>

            {onSimulate && (
                <button
                    onClick={onSimulate}
                    className="w-full btn btn-primary text-sm"
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    압박 시뮬레이션
                </button>
            )}
        </div>
    );
}
