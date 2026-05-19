'use client';

import { useState } from 'react';
import KeyMomentPitch from '@/components/KeyMomentPitch';
import { useRecentMatches } from '@/hooks/useRecentMatches';
import { useChanceAnalysis } from '@/hooks/useChanceAnalysis';
import type { TeamStanding } from '@/types';
import styles from '@/app/page.module.css';

type PostSubTab = 'review' | 'missed' | 'concede';

interface Props {
  ourTeam: TeamStanding;
}

// 포스트매치 탭 - 경기 복기 / 놓친 찬스 / 실점 원인 (3 서브탭)
export default function PostmatchTab({ ourTeam }: Props) {
  const [subTab, setSubTab] = useState<PostSubTab>('review');
  const { matches: recentMatches } = useRecentMatches(ourTeam.team_id);
  const {
    selectedMatch,
    chanceAnalysis,
    loading: chanceLoading,
    load: loadChanceAnalysis,
    reset: resetChance,
  } = useChanceAnalysis();

  return (
    <div className={styles.preMatchSection}>
      <div className={styles.simSubTabs}>
        <button
          onClick={() => setSubTab('review')}
          className={`${styles.simSubTab} ${subTab === 'review' ? styles.simSubTabActive : ''}`}
        >
          경기 복기
        </button>
        <button
          onClick={() => setSubTab('missed')}
          className={`${styles.simSubTab} ${subTab === 'missed' ? styles.simSubTabActive : ''}`}
        >
          놓친 찬스
        </button>
        <button
          onClick={() => setSubTab('concede')}
          className={`${styles.simSubTab} ${subTab === 'concede' ? styles.simSubTabActive : ''}`}
        >
          실점 원인
        </button>
      </div>

      {subTab === 'review' && (
        <div className={styles.matchSection}>
          <div className={styles.matchAnalysisHeader}>
            <div className={styles.matchAnalysisTitle}>경기 복기</div>
            <p className={styles.matchAnalysisDesc}>
              분석할 경기를 선택하세요. 패배/무승부 경기에서{' '}
              <strong className={styles.matchHighlight}>승리할 수 있었던 기회</strong>를 찾아냅니다.
            </p>
          </div>

          {!selectedMatch && (
            <div className="fade-in">
              {recentMatches.length === 0 ? (
                <div className={`card ${styles.matchListEmpty}`}>
                  최근 경기 데이터를 불러오는 중입니다.
                </div>
              ) : (
                <div className={styles.matchList}>
                  {recentMatches
                    .filter((match) => {
                      const teamId = ourTeam.team_id;
                      const isHomeTeam = match.home_team_id === teamId;
                      const isAwayTeam = match.away_team_id === teamId;
                      if (match.result === 'draw') return true;
                      if (isHomeTeam && match.result === 'home_win') return false;
                      if (isAwayTeam && match.result === 'away_win') return false;
                      return true;
                    })
                    .map((match) => {
                      const isDraw = match.result === 'draw';
                      return (
                        <button
                          key={match.game_id}
                          onClick={() => loadChanceAnalysis(match.game_id)}
                          className={styles.matchButton}
                          style={{ borderLeft: `6px solid ${isDraw ? '#f59e0b' : '#ef4444'}` }}
                        >
                          <div>
                            <div className={styles.matchDate}>{match.date}</div>
                            <div className={styles.matchTeams}>
                              {match.home_team}{' '}
                              <span className={styles.matchVs}>vs</span> {match.away_team}
                            </div>
                            <div className={styles.matchHint}>
                              {isDraw ? '무승부 경기 · 놓친 찬스 확인' : '패배 경기 · 승리 기회 재구성'}
                            </div>
                          </div>
                          <div className={styles.matchRight}>
                            <div className={styles.matchScore}>{match.score}</div>
                            <div
                              className={styles.matchResult}
                              style={{ color: isDraw ? '#d97706' : '#dc2626' }}
                            >
                              {match.result_text}
                            </div>
                            <div className={styles.matchCta}>분석 보기</div>
                          </div>
                        </button>
                      );
                    })}
                </div>
              )}
            </div>
          )}

          {selectedMatch && (
            <div className="fade-in">
              <button onClick={resetChance} className={styles.analysisBack}>
                <span>←</span> 뒤로가기
              </button>

              {chanceLoading ? (
                <div className={`${styles.analysisLoading} animate-fade-in`}>분석 중입니다...</div>
              ) : chanceAnalysis ? (
                <div className="analysis-result animate-fade-in">
                  <div className={`card ${styles.analysisCard}`}>
                    <h3 className={styles.analysisCardTitle}>AI 분석 리포트</h3>
                    <div className={styles.analysisCardText}>{chanceAnalysis.summary}</div>
                  </div>

                  <div className={`card ${styles.analysisGrid}`}>
                    <h4 className={styles.analysisGridTitle}>결정적 장면 재구성</h4>
                    <div
                      className={styles.analysisGridList}
                      style={{
                        gridTemplateColumns: chanceAnalysis.chances.length > 1 ? '1fr 1fr' : '1fr',
                      }}
                    >
                      {chanceAnalysis.chances.map((chance, i) => (
                        <div key={i} className="card">
                          <KeyMomentPitch
                            moments={chance.key_moments}
                            teamName={chance.team_name}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </div>
      )}

      {subTab === 'missed' && (
        <div className={`card ${styles.preMatchCard}`}>
          <div className={styles.preMatchHeader}>
            <div>
              <div className={styles.preMatchTitle}>놓친 찬스</div>
              <div className={styles.preMatchSubtitle}>
                경기 중 결정짓지 못한 슈팅·돌파·세트피스 기회를 모아봅니다.
              </div>
            </div>
          </div>
          <div className={styles.detailHint}>
            준비 중입니다. xG 기반 결정적 찬스 누락 분석 모듈을 연결할 예정입니다.
          </div>
        </div>
      )}

      {subTab === 'concede' && (
        <div className={`card ${styles.preMatchCard}`}>
          <div className={styles.preMatchHeader}>
            <div>
              <div className={styles.preMatchTitle}>실점 원인</div>
              <div className={styles.preMatchSubtitle}>
                실점 장면을 역으로 추적하여 빌드업 단계의 약점을 진단합니다.
              </div>
            </div>
          </div>
          <div className={styles.detailHint}>
            준비 중입니다. 실점 전 5초간의 빌드업·수비 라인 분석 파이프라인을 연결할 예정입니다.
          </div>
        </div>
      )}
    </div>
  );
}
