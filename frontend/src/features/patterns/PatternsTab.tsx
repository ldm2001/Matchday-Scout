'use client';

import { useState } from 'react';
import PitchReplay from '@/components/PitchReplay';
import { useTeamPhases } from '@/hooks/useTeamPhases';
import { usePhaseReplay } from '@/hooks/usePhaseReplay';
import type { Pattern } from '@/types';
import styles from '@/app/page.module.css';

interface Props {
  teamId: number | null;
  patterns: Pattern[];
}

// 패턴 탭 - 공격 페이즈 리플레이 + TOP5 패턴 통계
export default function PatternsTab({ teamId, patterns }: Props) {
  const { phases } = useTeamPhases(teamId);
  const { events, selectedPhaseId, loading: replayLoading, loadReplay } = usePhaseReplay(teamId);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);

  // 리플레이 토글 시 isPlaying 초기화는 usePhaseReplay 내부에서 처리되지 않으므로 여기서
  // selectedPhaseId가 바뀌면 자동으로 정지 상태로 전환 (선택 직후 사용자가 명시 재생)

  return (
    <div className={styles.tabPaneFlex}>
      <div className={`card ${styles.patternsCard}`}>
        <div className={`card-title ${styles.patternsTitle}`}>경기 상황 리플레이</div>

        <div className={styles.phaseSection}>
          <p className={styles.phaseLabel}>공격 Phase 선택:</p>
          <div className={styles.phaseList}>
            {phases.slice(0, 10).map((ph, idx) => (
              <button
                key={ph.phase_id}
                onClick={() => {
                  setIsPlaying(false);
                  loadReplay(ph.phase_id);
                }}
                className={`${styles.phaseButton} ${selectedPhaseId === ph.phase_id ? styles.phaseButtonActive : styles.phaseButtonInactive}`}
              >
                <div className={styles.phaseTitle}>Phase {idx + 1}</div>
                <div className={styles.phaseMeta}>
                  패스 {ph.passes}회 · {Math.round(ph.duration)}초
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className={styles.patternLayout}>
          <div className={`${styles.patternReplay} ${replayLoading ? styles.replayEase : ''}`}>
            {replayLoading ? (
              <div className={styles.patternLoading}>로딩 중...</div>
            ) : events.length > 0 ? (
              <PitchReplay
                events={events}
                isPlaying={isPlaying}
                onPlayPause={() => setIsPlaying(!isPlaying)}
                playbackSpeed={playbackSpeed}
                onSpeedChange={setPlaybackSpeed}
              />
            ) : (
              <div className={styles.patternEmpty}>
                <p className={styles.patternEmptyText}>위에서 Phase를 선택하세요</p>
              </div>
            )}
          </div>

          <div className={styles.patternSide}>
            <div className={styles.patternSideTitle}>패턴 TOP 5</div>
            <div className={styles.patternSideList}>
              {patterns.slice(0, 5).map((pattern, i) => {
                const rate = Math.max(0, Math.min(100, Math.round(pattern.shot_conversion_rate * 100)));
                return (
                  <div key={pattern.cluster_id} className={styles.patternSideItem}>
                    <span className={styles.patternSideRank}>#{i + 1}</span>
                    <span className={styles.patternSideRate}>{rate}%</span>
                    <span className={styles.patternSideFreq}>{pattern.frequency}회</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
