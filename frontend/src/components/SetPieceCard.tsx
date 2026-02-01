// 세트피스 카드 컴포넌트 - 코너킥/프리킥 루틴 정보 표시
'use client';

import { SetPieceRoutine } from '@/types';

interface SetPieceCardProps {
    routine: SetPieceRoutine;
}

// 세트피스 유형, 스윙 타입, 타겟존 및 수비 제안 표시
export default function SetPieceCard({ routine }: SetPieceCardProps) {
    // 세트피스 유형별 아이콘 반환
    const getTypeIcon = (type: string) => {
        if (type.includes('Corner')) {
            return (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 21h18M3 3h18M3 12h18M12 3v18" />
                </svg>
            );
        }
        return (
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10" strokeWidth={2} />
                <circle cx="12" cy="12" r="3" strokeWidth={2} />
            </svg>
        );
    };

    const getZoneLabel = (zone: string) => {
        const labels: Record<string, string> = {
            'near_post': '니어 포스트',
            'far_post': '파 포스트',
            'central': '중앙',
            'edge_of_box': '박스 외곽',
        };
        return labels[zone] || zone;
    };

    const getSwingLabel = (swing: string) => {
        if (swing === 'inswing') return '인스윙';
        if (swing === 'outswing') return '아웃스윙';
        return '기타';
    };

    return (
        <div className="card card-hover animate-fade-in">
            <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${routine.type.includes('Corner') ? 'bg-orange-500/20 text-orange-400' : 'bg-purple-500/20 text-purple-400'
                        }`}>
                        {getTypeIcon(routine.type)}
                    </div>
                    <div>
                        <h3 className="font-semibold text-white">
                            {routine.type.includes('Corner') ? '코너킥' : '프리킥'} 루틴
                        </h3>
                        <p className="text-sm text-slate-400">
                            {getSwingLabel(routine.swing_type)} • {getZoneLabel(routine.primary_zone)}
                        </p>
                    </div>
                </div>
                <div className="text-right">
                    <p className={`text-xl font-bold ${routine.shot_rate >= 0.3 ? 'text-red-400' : routine.shot_rate >= 0.15 ? 'text-yellow-400' : 'text-slate-400'}`}>
                        {(routine.shot_rate * 100).toFixed(0)}%
                    </p>
                    <p className="text-xs text-slate-500">슈팅 전환</p>
                </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="p-2 bg-slate-800/50 rounded text-center">
                    <p className="text-lg font-bold text-white">{routine.frequency}</p>
                    <p className="text-xs text-slate-400">발생 횟수</p>
                </div>
                <div className="p-2 bg-slate-800/50 rounded text-center">
                    <p className="text-lg font-bold text-white">{getZoneLabel(routine.primary_zone)}</p>
                    <p className="text-xs text-slate-400">주요 타겟</p>
                </div>
            </div>

            <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                <div className="flex items-start gap-2">
                    <svg className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <p className="text-sm text-amber-200">{routine.defense_suggestion}</p>
                </div>
            </div>
        </div>
    );
}
