'use client';

import type { TeamAnalysis } from '@/lib/api';
import type { Pattern, Hub, SetPieceRoutine } from '@/types';
import styles from '@/app/page.module.css';

interface Props {
  patterns: Pattern[];
  hubs: Hub[];
  setpieces: SetPieceRoutine[];
  patternsLoading: boolean;
  hubsLoading: boolean;
  setpiecesLoading: boolean;
  analysis: TeamAnalysis | null;
}

const sf = (val: number, d: number = 1) => (Number.isFinite(val) ? val.toFixed(d) : (0).toFixed(d));

const computeCount = (loading: boolean, arr: { length: number }): string | number =>
  loading && arr.length === 0 ? '—' : arr.length;

const scoreColor = (score: number): string => {
  if (score >= 70) return '#16a34a';
  if (score >= 50) return '#f59e0b';
  return '#dc2626';
};

// 팀 개요 탭 - 패턴/세트피스/허브 카운트 + 위험 패턴/압박 타겟 + AI 팀 분석
export default function OverviewTab({
  patterns,
  hubs,
  setpieces,
  patternsLoading,
  hubsLoading,
  setpiecesLoading,
  analysis,
}: Props) {
  const patternCount = computeCount(patternsLoading, patterns);
  const setpieceCount = computeCount(setpiecesLoading, setpieces);
  const hubCount = computeCount(hubsLoading, hubs);
  const topPattern = patterns[0];
  const topHub = hubs[0];

  return (
    <div className={styles.overviewScroll}>
      <div className="stats-grid">
        <div className="stat-card">
          <div
            className={`stat-value red ${patternCount === '—' ? 'stat-value-pending' : ''}`}
            key={`p-${patternCount}`}
          >
            {patternCount}
          </div>
          <div className="stat-label">공격 패턴</div>
        </div>
        <div className="stat-card">
          <div
            className={`stat-value blue ${setpieceCount === '—' ? 'stat-value-pending' : ''}`}
            key={`s-${setpieceCount}`}
          >
            {setpieceCount}
          </div>
          <div className="stat-label">세트피스</div>
        </div>
        <div className="stat-card">
          <div
            className={`stat-value green ${hubCount === '—' ? 'stat-value-pending' : ''}`}
            key={`h-${hubCount}`}
          >
            {hubCount}
          </div>
          <div className="stat-label">빌드업 허브</div>
        </div>
      </div>

      {topPattern && (
        <div className="card card-risk">
          <div className="card-title">가장 위험한 패턴</div>
          <div className={`pattern-grid ${styles.patternGridSingle}`}>
            <div className={styles.patternStatGrid}>
              <div>
                <div className={`pattern-stat-value ${styles.patternHighlight}`}>
                  {sf(topPattern.shot_conversion_rate * 100)}%
                </div>
                <div className="pattern-stat-label">슈팅 전환율</div>
              </div>
              <div>
                <div className="pattern-stat-value">{topPattern.frequency}</div>
                <div className="pattern-stat-label">발생 횟수</div>
              </div>
              <div>
                <div className="pattern-stat-value">{sf(topPattern.avg_passes)}</div>
                <div className="pattern-stat-label">평균 패스</div>
              </div>
              <div>
                <div className="pattern-stat-value">{sf(topPattern.avg_duration, 0)}초</div>
                <div className="pattern-stat-label">평균 시간</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {topHub && (
        <div className="card">
          <div className="card-title">최우선 압박 타겟</div>
          <div className="hub-card">
            <div className="hub-avatar">{topHub.position}</div>
            <div className="hub-info">
              <h4>{topHub.player_name}</h4>
              <p>
                허브 점수 {sf(topHub.hub_score * 100, 0)} • 패스 {topHub.passes_made}회
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 팀 AI 분석 */}
      <div className={styles.analysisSection}>
        <div className={`card ${styles.teamAnalysisCard}`}>
          {!analysis ? (
            <div className={styles.panelPlaceholder}>AI 팀 분석 불러오는 중...</div>
          ) : (
            <>
              <div className={`card-title ${styles.teamAnalysisTitle}`}>
                AI 팀 분석
                <span
                  className={styles.teamAnalysisBadge}
                  style={{ background: scoreColor(analysis.overall_score) }}
                >
                  {analysis.overall_score}점
                </span>
              </div>

              <p className={styles.teamAnalysisSummary}>{analysis.summary}</p>

              <div className={styles.analysisSplitGrid}>
                {/* 강점 */}
                <div className={styles.strengthCard}>
                  <h4 className={styles.strengthTitle}>강점</h4>
                  {analysis.strengths.length > 0 ? (
                    analysis.strengths.map((s, i) => (
                      <div key={i} className={styles.analysisItem}>
                        <div className={styles.analysisItemHead}>
                          <span className={styles.strengthItemTitle}>{s.title}</span>
                          <span className={styles.strengthScore}>{s.score}</span>
                        </div>
                        <p className={styles.strengthDesc}>{s.description}</p>
                      </div>
                    ))
                  ) : (
                    <p className={styles.analysisEmpty}>분석 중...</p>
                  )}
                </div>

                {/* 약점 */}
                <div className={styles.weaknessCard}>
                  <h4 className={styles.weaknessTitle}>개선 필요</h4>
                  {analysis.weaknesses.length > 0 ? (
                    analysis.weaknesses.map((w, i) => (
                      <div key={i} className={styles.analysisItem}>
                        <div className={styles.analysisItemHead}>
                          <span className={styles.weaknessItemTitle}>{w.title}</span>
                          <span className={styles.weaknessScore}>{w.score}</span>
                        </div>
                        <p className={styles.weaknessDesc}>{w.description}</p>
                      </div>
                    ))
                  ) : (
                    <p className={styles.analysisEmpty}>약점 없음</p>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
