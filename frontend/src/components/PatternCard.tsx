'use client';

import { Pattern } from '@/types';

interface PatternCardProps {
    pattern: Pattern;
    rank: number;
    onViewReplay?: () => void;
}

export default function PatternCard({ pattern, rank, onViewReplay }: PatternCardProps) {
    const getRankBadge = (rank: number) => {
        const colors: Record<number, string> = {
            1: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
            2: 'bg-slate-400/20 text-slate-300 border-slate-400/30',
            3: 'bg-amber-700/20 text-amber-500 border-amber-600/30',
        };
        return colors[rank] || 'bg-slate-600/20 text-slate-400 border-slate-500/30';
    };

    const getConversionColor = (rate: number) => {
        if (rate >= 0.2) return 'text-red-400';
        if (rate >= 0.1) return 'text-yellow-400';
        return 'text-slate-400';
    };

    return (
        <div className="card card-hover animate-fade-in">
            <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                    <span className={`px-2 py-1 text-xs font-bold rounded border ${getRankBadge(rank)}`}>
                        #{rank}
                    </span>
                    <div>
                        <h3 className="font-semibold text-white">공격 패턴</h3>
                        <p className="text-sm text-slate-400">
                            {pattern.avg_start_zone.replace('_', ' → ')} → {pattern.avg_end_zone.replace('_', ' ')}
                        </p>
                    </div>
                </div>
                <span className={`text-2xl font-bold ${getConversionColor(pattern.shot_conversion_rate)}`}>
                    {(pattern.shot_conversion_rate * 100).toFixed(1)}%
                </span>
            </div>

            <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="text-center p-2 bg-slate-800/50 rounded">
                    <p className="text-2xl font-bold text-white">{pattern.frequency}</p>
                    <p className="text-xs text-slate-400">발생 횟수</p>
                </div>
                <div className="text-center p-2 bg-slate-800/50 rounded">
                    <p className="text-2xl font-bold text-white">{pattern.avg_passes.toFixed(1)}</p>
                    <p className="text-xs text-slate-400">평균 패스</p>
                </div>
                <div className="text-center p-2 bg-slate-800/50 rounded">
                    <p className="text-2xl font-bold text-white">{pattern.avg_duration.toFixed(0)}s</p>
                    <p className="text-xs text-slate-400">평균 시간</p>
                </div>
            </div>

            <div className="mb-4">
                <p className="text-xs text-slate-400 mb-2">주요 시퀀스</p>
                <div className="flex flex-wrap gap-1">
                    {pattern.common_sequences.slice(0, 2).map((seq, i) => (
                        <span key={i} className="text-xs px-2 py-1 bg-slate-700 rounded text-slate-300">
                            {seq.split('_').slice(0, 4).join(' → ')}
                        </span>
                    ))}
                </div>
            </div>

            {onViewReplay && (
                <button
                    onClick={onViewReplay}
                    className="w-full btn btn-secondary text-sm"
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    패턴 리플레이
                </button>
            )}
        </div>
    );
}
