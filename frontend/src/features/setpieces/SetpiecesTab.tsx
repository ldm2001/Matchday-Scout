'use client';

import { useState } from 'react';
import SetpiecePitch from '@/components/SetpiecePitch';
import type { SetPieceRoutine } from '@/types';
import styles from '@/app/page.module.css';

interface Props {
  teamId: number | null;
  setpieces: SetPieceRoutine[];
  loading: boolean;
}

const sf = (val: number, d: number = 1) => (Number.isFinite(val) ? val.toFixed(d) : (0).toFixed(d));

const ZONE_MAP: Record<string, string> = {
  far_post: '먼 포스트',
  near_post: '가까운 포스트',
  center: '중앙',
  central: '중앙',
  penalty_spot: '페널티 스팟',
  six_yard: '6야드 박스',
  edge_box: '박스 경계',
  edge_of_box: '박스 경계',
  unknown: '미정',
  Unknown: '미정',
  '': '미정',
};

// 세트피스 탭 - 코너킥/프리킥 루틴 navigation + 피치 시각화
export default function SetpiecesTab({ teamId, setpieces, loading }: Props) {
  const [setpieceIndex, setSetpieceIndex] = useState(0);
  const [lastTeamId, setLastTeamId] = useState(teamId);

  // 팀 전환 시 인덱스 리셋 (effect 대신 render-time 동기화)
  if (teamId !== lastTeamId) {
    setLastTeamId(teamId);
    setSetpieceIndex(0);
  }

  if (setpieces.length === 0) {
    return (
      <div className={`card ${styles.setpieceEmpty}`}>
        {loading ? '세트피스 데이터를 불러오는 중...' : '세트피스 데이터가 없습니다.'}
      </div>
    );
  }

  const current = setpieces[setpieceIndex];
  const zone = current?.primary_zone || '';
  const isLast = setpieceIndex === setpieces.length - 1;
  const isFirst = setpieceIndex === 0;

  return (
    <div className={styles.setpieceCard}>
      {/* 상단 네비게이션 */}
      <div className={styles.setpieceNav}>
        <button
          onClick={() => setSetpieceIndex(Math.max(0, setpieceIndex - 1))}
          disabled={isFirst}
          className={`${styles.setpieceNavButton} ${isFirst ? styles.setpieceNavButtonDisabled : styles.setpieceNavButtonActive}`}
        >
          ←
        </button>

        <div className={styles.setpieceInfo}>
          <span
            className={`${styles.setpieceTag} ${current?.type.includes('Corner') ? styles.setpieceTagCorner : styles.setpieceTagFree}`}
          >
            {current?.type.includes('Corner') ? '코너킥' : '프리킥'}
          </span>
          <span className={styles.setpieceRate}>
            슈팅 전환율 {sf((current?.shot_rate ?? 0) * 100, 0)}%
          </span>
          <span className={styles.setpieceIndex}>
            {setpieceIndex + 1} / {setpieces.length}
          </span>
        </div>

        <button
          onClick={() => setSetpieceIndex(Math.min(setpieces.length - 1, setpieceIndex + 1))}
          disabled={isLast}
          className={`${styles.setpieceNavButton} ${isLast ? styles.setpieceNavButtonDisabled : styles.setpieceNavButtonActive}`}
        >
          →
        </button>
      </div>

      {/* 피치 시각화 */}
      <div className={styles.setpiecePitch}>
        <SetpiecePitch routine={current} />
      </div>

      {/* 하단 통계 */}
      <div className={styles.setpieceStats}>
        <div className={styles.setpieceStat}>
          <div className={styles.setpieceStatValue}>{current?.frequency}</div>
          <div className={styles.setpieceStatLabel}>발생 횟수</div>
        </div>
        <div className={styles.setpieceStat}>
          <div className={styles.setpieceStatValue}>
            {current?.swing_type === 'inswing' ? '인스윙' : '아웃스윙'}
          </div>
          <div className={styles.setpieceStatLabel}>킥 타입</div>
        </div>
        <div className={styles.setpieceStat}>
          <div className={styles.setpieceStatValue}>{ZONE_MAP[zone] || zone}</div>
          <div className={styles.setpieceStatLabel}>타겟존</div>
        </div>
      </div>

      {/* 수비 제안 */}
      <div className={styles.setpieceSuggest}>{current?.defense_suggestion}</div>
    </div>
  );
}
