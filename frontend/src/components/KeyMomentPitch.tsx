'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { KeyMoment } from '@/lib/api';
import styles from './KeyMomentPitch.module.css';

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

const toNum = (val: unknown): number | null => {
    if (val === null || val === undefined) return null;
    const num = Number(val);
    return Number.isFinite(num) ? num : null;
};

const toPct = (val: unknown): number | null => {
    const num = toNum(val);
    if (num === null) return null;
    return num <= 1 ? num * 100 : num;
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
    const trailStop1 = {
        x: actualPx.x + (targetPx.x - actualPx.x) * 0.35,
        y: actualPx.y + (targetPx.y - actualPx.y) * 0.35
    };
    const trailStop2 = {
        x: actualPx.x + (targetPx.x - actualPx.x) * 0.7,
        y: actualPx.y + (targetPx.y - actualPx.y) * 0.7
    };

    return (
        <div className={styles.miniPitch}>
            <div className={styles.miniPitchInner}>
                <div className={styles.miniPitchGrass} />

                {/* Lines */}
                <svg viewBox="0 0 150 97" className={styles.miniPitchSvg}>
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
                <div
                    className={`${styles.miniMarker} ${styles.miniMarkerActual}`}
                    style={{
                        left: actualPx.x - 6,
                        top: actualPx.y - 6,
                    }}
                />

                {/* Suggest marker (green) */}
                <div
                    className={`${styles.miniMarker} ${styles.miniMarkerTarget}`}
                    style={{
                        left: targetPx.x - 6,
                        top: targetPx.y - 6,
                    }}
                />

                {/* Relocation path */}
                <svg
                    viewBox="0 0 150 97"
                    className={styles.miniPitchSvg}
                >
                    <line
                        x1={actualPx.x + 8}
                        y1={actualPx.y}
                        x2={targetPx.x - 8}
                        y2={targetPx.y}
                        className={styles.miniPathLine}
                    />
                    <circle cx={trailStop1.x} cy={trailStop1.y} r="2.2" className={styles.miniPathDot} />
                    <circle cx={trailStop2.x} cy={trailStop2.y} r="2.2" className={styles.miniPathDot} />
                </svg>

                {/* Click hint */}
                <div className={styles.miniHint}>
                    🔍 3D
                </div>
            </div>
        </div>
    );
}

// Modal component
function Modal3D({ moment, onClose, teamName }: { moment: KeyMoment; onClose: () => void; teamName: string }) {
    const [pitchSize, setPitchSize] = useState(() => {
        if (typeof window === 'undefined') return { width: 640, height: 410 };
        const maxWidth = Math.min(720, window.innerWidth - 80);
        const width = Math.max(320, maxWidth);
        return { width, height: Math.round(width * 0.64) };
    });

    useEffect(() => {
        const handleResize = () => {
            const maxWidth = Math.min(720, window.innerWidth - 80);
            const width = Math.max(320, maxWidth);
            setPitchSize({ width, height: Math.round(width * 0.64) });
        };
        handleResize();
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    const actualXg = toPct(moment.failure_analysis?.xg);
    const expectedXg = toPct(moment.suggestion?.expected_xg);
    const deltaXg = actualXg !== null && expectedXg !== null ? expectedXg - actualXg : null;
    const deltaLabel = deltaXg !== null
        ? `${deltaXg > 0 ? '+' : ''}${deltaXg.toFixed(1)}%p`
        : (moment.suggestion?.xg_improvement || '—');

    const distance = toNum(moment.original_situation?.distance_to_goal);
    const distanceLabel = distance !== null ? `${distance.toFixed(1)}m` : '—';

    const zoneMap: Record<string, string> = {
        central: '중앙',
        center: '중앙',
        left: '좌측',
        right: '우측',
        near_post: '가까운 포스트',
        far_post: '먼 포스트',
        penalty_spot: '페널티 스팟',
        six_yard: '6야드 박스',
        edge_box: '박스 경계',
        edge_of_box: '박스 경계',
    };
    const zoneKey = moment.original_situation?.zone;
    const zoneLabel = zoneKey ? (zoneMap[zoneKey] || zoneKey) : '—';

    const failureReasons = (moment.failure_analysis?.reasons || []).filter(Boolean).slice(0, 2).join(' · ') || '—';
    const suggestionText = moment.suggestion?.description || (moment.suggestion?.reasons || []).join(' · ') || '—';
    const situationText = moment.original_situation?.description || moment.action || '—';

    return (
        <div
            onClick={onClose}
            className={`${styles.modalOverlay} fade-in`}
        >
            <div
                onClick={(e) => e.stopPropagation()}
                className={`${styles.modalPanel} animate-fade-in`}
            >
                <div className={styles.modalGlow} />

                <div className={styles.modalBody}>
                    <div className={styles.modalHeader}>
                        <div>
                            <div className={styles.modalMeta}>
                                프리매치 인사이트 · {teamName || '팀 정보'}
                            </div>
                            <div className={styles.modalTitle}>
                                {moment.player} <span className={styles.modalDivider}>·</span> {moment.time_display || '시간 정보 없음'}
                            </div>
                        </div>
                        <button
                            onClick={onClose}
                            className={styles.modalClose}
                        >
                            닫기
                        </button>
                    </div>

                    <div className={styles.modalContent}>
                        <div className={styles.chipRow}>
                            <span className={`${styles.chip} ${styles.chipPrimary}`}>
                                {moment.player_position || '포지션'}
                            </span>
                            <span className={`${styles.chip} ${styles.chipNeutral}`}>
                                {moment.action || '플레이'}
                            </span>
                            <span className={`${styles.chip} ${styles.chipDanger}`}>
                                {moment.result || '결과'}
                            </span>
                        </div>

                        <div className={styles.metricGrid}>
                            <div className={styles.metricCard}>
                                <div className={styles.metricLabel}>실제 xG</div>
                                <div className={styles.metricValue}>
                                    {actualXg !== null ? `${actualXg.toFixed(1)}%` : '—'}
                                </div>
                                <div className={styles.metricFoot}>{distanceLabel} · {zoneLabel}</div>
                            </div>
                            <div className={`${styles.metricCard} ${styles.metricCardSuggest}`}>
                                <div className={`${styles.metricLabel} ${styles.metricLabelSuggest}`}>AI 제안 xG</div>
                                <div className={`${styles.metricValue} ${styles.metricValueSuggest}`}>
                                    {expectedXg !== null ? `${expectedXg.toFixed(1)}%` : '—'}
                                </div>
                                <div className={`${styles.metricFoot} ${styles.metricFootSuggest}`}>추천 위치 기준</div>
                            </div>
                            <div className={`${styles.metricCard} ${styles.metricCardDelta}`}>
                                <div className={`${styles.metricLabel} ${styles.metricLabelDelta}`}>개선 폭</div>
                                <div className={`${styles.metricValue} ${styles.metricValueDelta}`}>
                                    {deltaLabel}
                                </div>
                                <div className={`${styles.metricFoot} ${styles.metricFootDelta}`}>xG 기준</div>
                            </div>
                        </div>

                        <div className={styles.modalGrid}>
                            <div className={styles.pitchCard}>
                                <div className={styles.pitchTitle}>3D 포지셔닝</div>
                                <div className={styles.pitchWrap}>
                                    <Pitch3D moment={moment} width={pitchSize.width} height={pitchSize.height} />
                                </div>
                                <div className={styles.legend}>
                                    <span className={`${styles.legendItem} ${styles.legendLabelActual}`}>
                                        <span className={`${styles.legendSwatch} ${styles.legendActual}`} />
                                        실제 위치
                                    </span>
                                    <span className={`${styles.legendItem} ${styles.legendLabelTarget}`}>
                                        <span className={`${styles.legendSwatch} ${styles.legendTarget}`} />
                                        AI 제안
                                    </span>
                                    <span className={`${styles.legendItem} ${styles.legendLabelPath}`}>
                                        <span className={styles.legendPath} />
                                        재배치 경로
                                    </span>
                                </div>
                            </div>

                            <div className={styles.summaryStack}>
                                <div className={styles.summaryCard}>
                                    <div className={`${styles.summaryTitle} ${styles.summaryTitleSituation}`}>
                                        상황 요약
                                    </div>
                                    <div className={styles.summaryText}>
                                        {situationText}
                                    </div>
                                </div>

                                <div className={`${styles.summaryCard} ${styles.summaryCardFail}`}>
                                    <div className={`${styles.summaryTitle} ${styles.summaryTitleFail}`}>
                                        실패 원인
                                    </div>
                                    <div className={`${styles.summaryText} ${styles.summaryTextFail}`}>
                                        {failureReasons}
                                    </div>
                                </div>

                                <div className={`${styles.summaryCard} ${styles.summaryCardSuggest}`}>
                                    <div className={`${styles.summaryTitle} ${styles.summaryTitleSuggest}`}>
                                        AI 제안
                                    </div>
                                    <div className={`${styles.summaryText} ${styles.summaryTextSuggest}`}>
                                        {suggestionText}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default function KeyMomentPitch({ moments, teamName }: KeyMomentPitchProps) {
    const [selectedMoment, setSelectedMoment] = useState<KeyMoment | null>(null);

    useEffect(() => {
        import('./Pitch3D');
    }, []);

    if (moments.length === 0) {
        return (
            <div className={styles.empty}>
                분석할 찬스가 없습니다
            </div>
        );
    }

    return (
        <div>
            {moments.map((moment, i) => (
                <div key={i} className={styles.momentCard}>
                    {/* 헤더 */}
                    <div className={styles.momentHeader}>
                        <div className={styles.momentHeaderLeft}>
                            <span className={styles.positionBadge}>
                                {moment.player_position || 'FW'}
                            </span>
                            <span className={styles.playerName}>
                                {moment.player}
                            </span>
                        </div>
                        <span className={styles.timeBadge}>
                            {moment.time_display}
                        </span>
                    </div>

                    {/* 컨텐츠 */}
                    <div className={styles.momentBody}>
                        {/* 3D 미니 피치 - 클릭하면 모달 */}
                        <div className={styles.momentPitch} onClick={() => setSelectedMoment(moment)}>
                            <MiniPitch3D moment={moment} index={i} />
                        </div>

                        {/* 분석 정보 */}
                        <div className={styles.momentInfo}>
                            <div className={`${styles.infoBlock} ${styles.infoBlockFail}`}>
                                <div className={`${styles.infoTitle} ${styles.infoTitleFail}`}>실패 원인</div>
                                <div className={styles.infoText}>
                                    {(moment.failure_analysis?.reasons || []).slice(0, 2).join(' ')}
                                </div>
                                {(moment.failure_analysis?.xg ?? 0) > 0 && (
                                    <div className={styles.infoXg}>xG: {Math.round(moment.failure_analysis?.xg ?? 0)}%</div>
                                )}
                            </div>

                            <div className={`${styles.infoBlock} ${styles.infoBlockSuggest}`}>
                                <div className={`${styles.infoTitle} ${styles.infoTitleSuggest}`}>이렇게 했다면</div>
                                <div className={styles.infoText}>
                                    {moment.suggestion?.description || (moment.suggestion?.reasons || []).join(' ')}
                                </div>
                                {moment.suggestion?.expected_xg && (
                                    <div className={styles.infoSuggestXg}>
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
                <Modal3D moment={selectedMoment} teamName={teamName} onClose={() => setSelectedMoment(null)} />
            )}
        </div>
    );
}
