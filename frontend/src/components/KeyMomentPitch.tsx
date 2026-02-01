// 키 모멘트 피치 컴포넌트 - 놓친 찬스와 AI 추천 포지션 시각화
'use client';

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import dynamic from 'next/dynamic';
import { KeyMoment } from '@/lib/api';
import styles from './KeyMomentPitch.module.css';

// 3D 피치 컴포넌트 동적 로딩 (SSR 비활성화)
const Pitch3D = dynamic(() => import('./Pitch3D'), { ssr: false });

interface KeyMomentPitchProps {
    moments: KeyMoment[];
    teamName: string;
}

// 안전한 숫자 변환 (null/undefined/NaN 처리)
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

const cleanText = (val: unknown, fallback: string): string => {
    if (val === null || val === undefined) return fallback;
    const text = String(val).trim();
    if (!text) return fallback;
    const lower = text.toLowerCase();
    if (lower === 'nan' || lower === 'none' || lower === 'null' || lower === 'undefined') return fallback;
    return text;
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
                    <rect x="2" y="2" width="146" height="93" fill="none" stroke="#cbd5e1" strokeWidth="1.5" />
                    {/* Center line */}
                    <line x1="75" y1="2" x2="75" y2="95" stroke="#cbd5e1" strokeWidth="1" />
                    {/* Center circle */}
                    <circle cx="75" cy="48.5" r="12" fill="none" stroke="#cbd5e1" strokeWidth="1" />
                    {/* Right penalty box */}
                    <rect x="126" y="20" width="22" height="57" fill="none" stroke="#cbd5e1" strokeWidth="1" />
                    {/* Right goal box */}
                    <rect x="140" y="33" width="8" height="31" fill="none" stroke="#cbd5e1" strokeWidth="1" />
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
                    확대
                </div>
            </div>
        </div>
    );
}

// Modal component
function Modal3D({ moment, onClose, teamName }: { moment: KeyMoment; onClose: () => void; teamName: string }) {
    const [pitchSize, setPitchSize] = useState(() => {
        if (typeof window === 'undefined') return { width: 640, height: 410 };
        const maxWidth = Math.min(680, window.innerWidth - 80);
        const width = Math.max(320, maxWidth);
        return { width, height: Math.round(width * 0.48) };
    });

    useEffect(() => {
        const handleResize = () => {
            const maxWidth = Math.min(680, window.innerWidth - 80);
            const width = Math.max(320, maxWidth);
            setPitchSize({ width, height: Math.round(width * 0.48) });
        };
        handleResize();
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    const actualPos = {
        x: safeNum(moment.position?.x, 75),
        y: safeNum(moment.position?.y, 34),
    };
    const targetPos = {
        x: safeNum(moment.suggestion?.target_position?.x || moment.suggestion?.target_x, actualPos.x + 8),
        y: safeNum(moment.suggestion?.target_position?.y || moment.suggestion?.target_y, actualPos.y),
    };
    const shiftDistance = Math.hypot(targetPos.x - actualPos.x, targetPos.y - actualPos.y);
    const distanceRaw = toNum(moment.original_situation?.distance_to_goal);
    const goalDistance = distanceRaw ?? Math.hypot(105 - actualPos.x, 34 - actualPos.y);
    const actualCoord = `${actualPos.x.toFixed(1)}m, ${actualPos.y.toFixed(1)}m`;
    const targetCoord = `${targetPos.x.toFixed(1)}m, ${targetPos.y.toFixed(1)}m`;
    const moveLabel = `${shiftDistance.toFixed(1)}m`;
    const goalLabel = `${goalDistance.toFixed(1)}m`;

    const actualXg = toPct(moment.failure_analysis?.xg);
    const expectedXg = toPct(moment.suggestion?.expected_xg);
    const deltaXg = actualXg !== null && expectedXg !== null ? expectedXg - actualXg : null;
    const deltaLabel = deltaXg !== null
        ? `${deltaXg > 0 ? '+' : ''}${deltaXg.toFixed(1)}%p`
        : (moment.suggestion?.xg_improvement || '—');

    const distanceLabel = Number.isFinite(goalDistance) ? goalLabel : '—';

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
    const suggestionText = cleanText(
        moment.suggestion?.description || (moment.suggestion?.reasons || []).join(' · '),
        '—'
    );
    const situationText = cleanText(
        moment.original_situation?.description || moment.action,
        '—'
    );
    const positionLabel = cleanText(moment.player_position, '포지션');
    const actionLabel = cleanText(moment.action, '플레이');
    const resultLabel = cleanText(moment.result, '결과');
    const playerLabel = cleanText(moment.player, '선수 정보 없음');
    const timeLabel = cleanText(moment.time_display, '시간 정보 없음');

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
                        <div className={styles.headerLeft}>
                            <div className={styles.modalMeta}>
                                프리매치 인사이트 · {teamName || '팀 정보'}
                            </div>
                            <div className={styles.modalTitle}>
                                {playerLabel} <span className={styles.modalDivider}>·</span> {timeLabel}
                            </div>
                        </div>
                        <div className={styles.headerRight}>
                            <div className={styles.deltaPill}>
                                개선 {deltaLabel}
                            </div>
                            <button
                                onClick={onClose}
                                className={styles.modalClose}
                            >
                                닫기
                            </button>
                        </div>
                    </div>

                    <div className={styles.modalContent}>
                        <div className={styles.metaRow}>
                            <span className={`${styles.tag} ${styles.tagPrimary}`}>
                                {positionLabel}
                            </span>
                            <span className={`${styles.tag} ${styles.tagNeutral}`}>
                                {actionLabel}
                            </span>
                            <span className={`${styles.tag} ${styles.tagDanger}`}>
                                {resultLabel}
                            </span>
                            <span className={`${styles.tag} ${styles.tagGhost}`}>
                                {distanceLabel}
                            </span>
                            <span className={`${styles.tag} ${styles.tagGhost}`}>
                                {zoneLabel}
                            </span>
                        </div>

                        <div className={styles.statStrip}>
                            <div className={styles.statItem}>
                                <div className={styles.statLabel}>실제 위치</div>
                                <div className={styles.statValue}>{actualCoord}</div>
                            </div>
                            <div className={styles.statItem}>
                                <div className={styles.statLabel}>추천 위치</div>
                                <div className={styles.statValue}>{targetCoord}</div>
                            </div>
                            <div className={styles.statItem}>
                                <div className={styles.statLabel}>이동 거리</div>
                                <div className={styles.statValue}>{moveLabel}</div>
                            </div>
                            <div className={styles.statItem}>
                                <div className={styles.statLabel}>골까지 거리</div>
                                <div className={styles.statValue}>{goalLabel}</div>
                            </div>
                        </div>

                        <div className={styles.scoreRow}>
                            <div className={styles.scoreCard}>
                                <div className={styles.scoreLabel}>실제 xG</div>
                                <div className={styles.scoreValue}>
                                    {actualXg !== null ? `${actualXg.toFixed(1)}%` : '—'}
                                </div>
                                <div className={styles.scoreFoot}>실제 위치</div>
                            </div>
                            <div className={styles.scoreBridge}>
                                <span className={styles.scoreArrow}>→</span>
                                <span className={styles.scoreDelta}>{deltaLabel}</span>
                            </div>
                            <div className={`${styles.scoreCard} ${styles.scoreCardSuggest}`}>
                                <div className={styles.scoreLabel}>AI 제안 xG</div>
                                <div className={`${styles.scoreValue} ${styles.scoreValueSuggest}`}>
                                    {expectedXg !== null ? `${expectedXg.toFixed(1)}%` : '—'}
                                </div>
                                <div className={styles.scoreFoot}>추천 위치 기준</div>
                            </div>
                        </div>

                        <div className={styles.modalGrid}>
                            <div className={styles.pitchCard}>
                                <div className={styles.pitchHead}>
                                    <div className={styles.pitchTitle}>포지셔닝 맵</div>
                                    <div className={styles.pitchMeta}>탑뷰 · 실제 vs AI</div>
                                </div>
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
                                <div className={`${styles.summaryCard} ${styles.summaryCardSituation}`}>
                                    <div className={styles.summaryHeader}>
                                        <span className={`${styles.summaryBadge} ${styles.summaryBadgeSituation}`}>상황</span>
                                        <span className={styles.summaryHeading}>상황 요약</span>
                                    </div>
                                    <div className={styles.summaryText}>{situationText}</div>
                                </div>

                                <div className={`${styles.summaryCard} ${styles.summaryCardFail}`}>
                                    <div className={styles.summaryHeader}>
                                        <span className={`${styles.summaryBadge} ${styles.summaryBadgeFail}`}>원인</span>
                                        <span className={styles.summaryHeading}>실패 원인</span>
                                    </div>
                                    <div className={styles.summaryText}>{failureReasons}</div>
                                </div>

                                <div className={`${styles.summaryCard} ${styles.summaryCardSuggest}`}>
                                    <div className={styles.summaryHeader}>
                                        <span className={`${styles.summaryBadge} ${styles.summaryBadgeSuggest}`}>제안</span>
                                        <span className={styles.summaryHeading}>AI 제안</span>
                                    </div>
                                    <div className={styles.summaryText}>{suggestionText}</div>
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

    useEffect(() => {
        if (!selectedMoment || typeof document === 'undefined') return;
        const prevOverflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        return () => {
            document.body.style.overflow = prevOverflow;
        };
    }, [selectedMoment]);

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
            {selectedMoment && typeof document !== 'undefined'
                ? createPortal(
                    <Modal3D moment={selectedMoment} teamName={teamName} onClose={() => setSelectedMoment(null)} />,
                    document.body
                )
                : null}
        </div>
    );
}
