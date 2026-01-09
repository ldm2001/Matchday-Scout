'use client';

import { VulnerabilityChain, PressingSimulation } from '@/types';

interface SimulationModalProps {
    isOpen: boolean;
    onClose: () => void;
    playerName: string;
    simulation: PressingSimulation;
    chain: VulnerabilityChain;
    summary: string;
}

export default function SimulationModal({
    isOpen,
    onClose,
    playerName,
    simulation,
    chain,
    summary,
}: SimulationModalProps) {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70">
            <div className="bg-slate-800 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto animate-fade-in">
                {/* Header */}
                <div className="sticky top-0 bg-slate-800 border-b border-slate-700 px-6 py-4 flex items-center justify-between">
                    <div>
                        <h2 className="text-xl font-bold text-white">압박 시뮬레이션</h2>
                        <p className="text-sm text-slate-400">타겟: {playerName}</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 rounded-lg hover:bg-slate-700 transition-colors"
                    >
                        <svg className="w-6 h-6 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <div className="p-6 space-y-6">
                    {/* Scenario Comparison */}
                    <div>
                        <h3 className="text-sm font-semibold text-slate-400 mb-3">시나리오 비교</h3>
                        <div className="grid grid-cols-2 gap-4">
                            {/* Scenario A: No Pressing */}
                            <div className="p-4 bg-slate-700/50 rounded-lg border border-slate-600">
                                <p className="text-sm text-slate-400 mb-2">{simulation.scenario_a.name}</p>
                                <p className="text-3xl font-bold text-white mb-1">
                                    {(simulation.scenario_a.pass_success_rate * 100).toFixed(1)}%
                                </p>
                                <p className="text-sm text-slate-400">패스 성공률</p>
                            </div>

                            {/* Scenario B: With Pressing */}
                            <div className="p-4 bg-blue-600/20 rounded-lg border border-blue-500/50">
                                <p className="text-sm text-blue-400 mb-2">{simulation.scenario_b.name}</p>
                                <p className="text-3xl font-bold text-blue-400 mb-1">
                                    {(simulation.scenario_b.pass_success_rate * 100).toFixed(1)}%
                                </p>
                                <p className="text-sm text-slate-400">예상 패스 성공률</p>
                                <p className="text-xs text-red-400 mt-2">
                                    ↓ {((simulation.scenario_a.pass_success_rate - simulation.scenario_b.pass_success_rate) * 100).toFixed(1)}%p 감소
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Vulnerability Chain */}
                    <div>
                        <h3 className="text-sm font-semibold text-slate-400 mb-3">약점 체인</h3>
                        <div className="relative">
                            {/* Chain steps */}
                            <div className="space-y-3">
                                {[chain.step1, chain.step2, chain.step3].map((step, i) => (
                                    <div key={i} className="flex items-start gap-4">
                                        <div className="flex flex-col items-center">
                                            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${i === 0 ? 'bg-blue-600 text-white' :
                                                    i === 1 ? 'bg-yellow-500 text-black' :
                                                        'bg-green-500 text-white'
                                                }`}>
                                                {i + 1}
                                            </div>
                                            {i < 2 && (
                                                <div className="w-0.5 h-6 bg-slate-600 mt-2" />
                                            )}
                                        </div>
                                        <div className="flex-1 pb-4">
                                            <p className="text-sm font-medium text-white">{step.action}</p>
                                            <p className="text-sm text-slate-400">{step.expected_result}</p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Expected Outcomes on Failure */}
                    <div>
                        <h3 className="text-sm font-semibold text-slate-400 mb-3">패스 실패 시 예상 후속 이벤트</h3>
                        <div className="space-y-2">
                            {Object.entries(simulation.on_failure_followups).slice(0, 5).map(([event, prob]) => (
                                <div key={event} className="flex items-center gap-3">
                                    <div className="flex-1">
                                        <div className="flex items-center justify-between mb-1">
                                            <span className="text-sm text-white">{event}</span>
                                            <span className="text-sm text-slate-400">{(prob * 100).toFixed(0)}%</span>
                                        </div>
                                        <div className="w-full bg-slate-700 rounded-full h-2">
                                            <div
                                                className="bg-blue-500 h-2 rounded-full"
                                                style={{ width: `${prob * 100}%` }}
                                            />
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Recommendation */}
                    <div className="p-4 bg-gradient-to-r from-blue-600/20 to-green-600/20 rounded-lg border border-blue-500/30">
                        <p className="text-sm font-semibold text-white mb-2">💡 전술 제안</p>
                        <p className="text-sm text-slate-300">{simulation.recommendation}</p>
                    </div>

                    {/* Summary */}
                    <div className="p-4 bg-slate-700 rounded-lg">
                        <p className="text-sm font-semibold text-white mb-1">📋 요약</p>
                        <p className="text-sm text-slate-300">{summary}</p>
                    </div>
                </div>

                {/* Footer */}
                <div className="sticky bottom-0 bg-slate-800 border-t border-slate-700 px-6 py-4 flex justify-end gap-3">
                    <button onClick={onClose} className="btn btn-secondary">
                        닫기
                    </button>
                </div>
            </div>
        </div>
    );
}
