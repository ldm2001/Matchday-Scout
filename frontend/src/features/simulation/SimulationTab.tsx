'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import { usePreMatchSim } from '@/hooks/usePreMatchSim';
import type { TeamStanding } from '@/types';
import styles from '@/app/page.module.css';

const ANALYSIS_GAMES = 100;

interface Props {
  ourTeam: TeamStanding;
  standings: TeamStanding[];
  teamLogo: (teamName: string) => string;
}

const pct = (val: number) => {
  if (!Number.isFinite(val)) return 0;
  const p = Math.abs(val) <= 1 ? val * 100 : val;
  return Math.max(-100, Math.min(100, p));
};
const fmtPct = (val: number) => `${pct(val).toFixed(1)}%`;

// 프리매치 탭 - 상대 선택 + 승부 예측 + 전술 제안 (예측/전술 2 서브탭)
export default function SimulationTab({ ourTeam, standings, teamLogo }: Props) {
  const [subTab, setSubTab] = useState<'predict' | 'tactics'>('predict');
  const [opponent, setOpponent] = useState<TeamStanding | null>(null);
  const [simPulse, setSimPulse] = useState(false);
  const opponentCacheRef = useRef<Record<number, number>>({});

  // 팀 전환 시 기본 상대 자동 선정 (캐시 우선, 없으면 가장 가까운 순위)
  // standings/캐시(외부 가변 상태) 동기화 — setState-in-effect 예외
  useEffect(() => {
    if (standings.length === 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setOpponent(null);
      return;
    }
    const cachedOpponentId = opponentCacheRef.current[ourTeam.team_id];
    const cachedOpponent = standings.find((team) => team.team_id === cachedOpponentId);
    if (cachedOpponent && cachedOpponent.team_id !== ourTeam.team_id) {
      setOpponent(cachedOpponent);
      return;
    }
    const candidates = standings.filter((team) => team.team_id !== ourTeam.team_id);
    if (candidates.length === 0) {
      setOpponent(null);
      return;
    }
    const nextOpponent = candidates.reduce((closest, team) => {
      const closestDiff = Math.abs(closest.rank - ourTeam.rank);
      const teamDiff = Math.abs(team.rank - ourTeam.rank);
      return teamDiff < closestDiff ? team : closest;
    }, candidates[0]);
    setOpponent((prev) =>
      prev && prev.team_id === nextOpponent.team_id ? prev : nextOpponent,
    );
    opponentCacheRef.current[ourTeam.team_id] = nextOpponent.team_id;
  }, [ourTeam, standings]);

  const { result: simResult, loading: simLoading, isStale: simStale, key: simKey, run } =
    usePreMatchSim(ourTeam, opponent);

  const canRunSim = Boolean(opponent);
  const simPending = canRunSim && !simResult;
  const simUpdating = simLoading || simStale;

  // 키/결과 변경 감지 → 렌더 중 펄스 트리거 (setState-in-effect 회피)
  const [pulseSeen, setPulseSeen] = useState<{ key: string | null; result: typeof simResult }>({
    key: null,
    result: null,
  });
  if (simKey && (pulseSeen.key !== simKey || pulseSeen.result !== simResult)) {
    setPulseSeen({ key: simKey, result: simResult });
    setSimPulse(true);
  }
  useEffect(() => {
    if (!simPulse) return;
    const timer = setTimeout(() => setSimPulse(false), 600);
    return () => clearTimeout(timer);
  }, [simPulse]);

  const handleOpponentSelect = useCallback(
    (team: TeamStanding) => {
      setOpponent(team);
      opponentCacheRef.current[ourTeam.team_id] = team.team_id;
    },
    [ourTeam.team_id],
  );

  const scenarios = simResult?.scenarios ?? [];
  const pickScenarioForTactic = (tactic: string) => {
    if (scenarios.length === 0) return null;
    const rules: Array<{ match: RegExp; keys: string[] }> = [
      { match: /허브|중앙|중원|압박/, keys: ['허브', '압박', '중앙'] },
      { match: /세트피스/, keys: ['세트피스'] },
      { match: /패턴|약점|루트/, keys: ['패턴', '약점'] },
      { match: /종합|전체|복합/, keys: ['종합'] },
    ];
    const rule = rules.find((item) => item.match.test(tactic));
    if (rule) {
      const matched = scenarios.find((sc) => rule.keys.some((key) => sc.scenario.includes(key)));
      if (matched) return matched;
    }
    return scenarios[0];
  };

  const renderProbBars = (prediction?: { win: number; draw: number; lose: number }) => {
    if (!prediction) {
      return <div className={styles.probHint}>상대팀을 선택하면 예측이 표시됩니다.</div>;
    }
    const rows = [
      { label: '승', value: pct(prediction.win), color: '#16a34a' },
      { label: '무', value: pct(prediction.draw), color: '#f59e0b' },
      { label: '패', value: pct(prediction.lose), color: '#ef4444' },
    ];
    return (
      <div className={styles.probRows}>
        {rows.map((row) => (
          <div key={row.label} className={styles.probRow}>
            <div className={styles.probLabel} style={{ color: row.color }}>
              {row.label}
            </div>
            <div className={styles.probTrack}>
              <div
                className={styles.probFill}
                style={{
                  width: `${Math.min(Math.max(row.value, 0), 100)}%`,
                  background: row.color,
                }}
              />
            </div>
            <div className={styles.probValue}>{row.value.toFixed(1)}%</div>
          </div>
        ))}
      </div>
    );
  };

  const renderProbSkeleton = () => (
    <div className={styles.probRows}>
      {[0, 1, 2].map((idx) => (
        <div key={idx} className={styles.probSkeletonRow} />
      ))}
    </div>
  );

  return (
    <div className={styles.preMatchSection}>
      <div className={styles.simSubTabs}>
        <button
          onClick={() => setSubTab('predict')}
          className={`${styles.simSubTab} ${subTab === 'predict' ? styles.simSubTabActive : ''}`}
        >
          예측
        </button>
        <button
          onClick={() => setSubTab('tactics')}
          className={`${styles.simSubTab} ${subTab === 'tactics' ? styles.simSubTabActive : ''}`}
        >
          전술 제안
        </button>
      </div>

      {subTab === 'predict' && (
        <div className={`card ${styles.preMatchCard} ${simPulse ? styles.simPulse : ''}`}>
          <div className={styles.preMatchHeader}>
            <div>
              <div className={styles.preMatchTitle}>프리매치 예측</div>
              <div className={styles.preMatchSubtitle}>
                최근 {ANALYSIS_GAMES}경기 기반 시뮬레이션
              </div>
            </div>
            <div className={styles.preMatchActions}>
              {simUpdating && <span className={styles.updateBadge}>업데이트 중</span>}
              <button
                onClick={() => {
                  if (opponent) run();
                }}
                disabled={!canRunSim || simLoading}
                className={`${styles.preMatchButton} ${canRunSim && !simLoading ? styles.preMatchButtonActive : styles.preMatchButtonDisabled}`}
              >
                {simLoading ? '계산 중...' : '재계산'}
              </button>
            </div>
          </div>

          <div className={styles.opponentLabel}>상대팀 선택</div>
          <div className={styles.opponentList}>
            {standings.map((team) => {
              const isSelf = ourTeam.team_id === team.team_id;
              const isActive = opponent?.team_id === team.team_id;
              return (
                <button
                  key={team.team_id}
                  onClick={() => {
                    if (!isSelf) handleOpponentSelect(team);
                  }}
                  disabled={isSelf}
                  className={`${styles.opponentButton} ${isActive ? styles.opponentButtonActive : ''} ${isSelf ? styles.opponentButtonDisabled : ''}`}
                >
                  <Image
                    src={teamLogo(team.team_name)}
                    alt={team.team_name}
                    className={styles.opponentLogo}
                    width={20}
                    height={20}
                    onError={(e) => {
                      e.currentTarget.style.visibility = 'hidden';
                    }}
                  />
                  <div className={styles.opponentInfo}>
                    <div className={styles.opponentName}>{team.team_name}</div>
                    <div className={styles.opponentRank}>
                      {team.rank}위 · {team.points}점
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
          <div className={styles.opponentHint}>
            상대팀을 클릭하면 자동으로 예측이 갱신됩니다.
          </div>

          <div
            className={`${styles.preMatchGrid} ${simStale ? styles.simDim : ''} ${simPulse ? styles.simPulse : ''}`}
          >
            <div className={styles.matchupCard}>
              <div className={styles.matchupLabel}>매치업</div>
              <div className={styles.matchupRow}>
                <div className={styles.matchupTeam}>
                  <Image
                    src={teamLogo(ourTeam.team_name)}
                    alt={ourTeam.team_name}
                    className="team-logo-lg"
                    width={48}
                    height={48}
                    onError={(e) => {
                      e.currentTarget.style.visibility = 'hidden';
                    }}
                  />
                  <div className={styles.matchupTeamInfo}>
                    <div className={styles.matchupTeamName}>{ourTeam.team_name}</div>
                    <div className={styles.matchupTeamMeta}>
                      {ourTeam.rank}위 · {ourTeam.points}점
                    </div>
                  </div>
                </div>
                <div className={styles.matchupVs}>VS</div>
                <div className={styles.matchupTeamRight}>
                  {opponent ? (
                    <>
                      <div className={styles.matchupTeamInfo}>
                        <div className={styles.matchupTeamName}>{opponent.team_name}</div>
                        <div className={styles.matchupTeamMeta}>
                          {opponent.rank}위 · {opponent.points}점
                        </div>
                      </div>
                      <Image
                        src={teamLogo(opponent.team_name)}
                        alt={opponent.team_name}
                        className="team-logo-lg"
                        width={48}
                        height={48}
                        onError={(e) => {
                          e.currentTarget.style.visibility = 'hidden';
                        }}
                      />
                    </>
                  ) : (
                    <div className={styles.matchupEmpty}>상대팀 선택</div>
                  )}
                </div>
              </div>
            </div>

            <div className={styles.probCard}>
              <div className={styles.probTitle}>기본 승부 예측</div>
              {simPending ? renderProbSkeleton() : renderProbBars(simResult?.base_prediction)}
            </div>

            <div className={styles.probCard}>
              <div className={styles.probTitle}>전술 적용 후</div>
              {simPending ? renderProbSkeleton() : renderProbBars(simResult?.optimal_prediction)}
            </div>
          </div>

          {simPending ? (
            <div className={styles.improvementPending}>승률 개선 계산 중...</div>
          ) : simResult ? (
            <div className={styles.improvement}>
              승률 개선 {simResult.win_improvement >= 0 ? '+' : ''}
              {pct(simResult.win_improvement).toFixed(1)}%p
              {simUpdating && <span className={styles.updateTag}>업데이트 중</span>}
            </div>
          ) : null}
        </div>
      )}

      {subTab === 'tactics' && (
        <div className={`card ${styles.preMatchCard} ${simPulse ? styles.simPulse : ''}`}>
          <div className={styles.preMatchHeader}>
            <div>
              <div className={styles.preMatchTitle}>전술 제안</div>
              <div className={styles.preMatchSubtitle}>예측 결과 기반 추천 전술과 시나리오</div>
            </div>
          </div>
          <div
            className={`${styles.preMatchDetailGrid} ${simStale ? styles.simDim : ''} ${simPulse ? styles.simPulse : ''}`}
          >
            <div className={styles.detailCard}>
              <div className={styles.detailHeader}>
                <div className={styles.detailTitle}>핵심 전술 제안</div>
                {simUpdating && <span className={styles.detailUpdate}>업데이트 중</span>}
              </div>
              {simPending ? (
                <div className={styles.detailHint}>시뮬레이션 결과를 기다리는 중...</div>
              ) : simResult?.tactical_suggestions?.length ? (
                <div className={styles.tacticList}>
                  {simResult.tactical_suggestions.slice(0, 3).map((s) => {
                    const relatedScenario = pickScenarioForTactic(s.tactic);
                    return (
                      <div key={`${s.priority}-${s.tactic}`} className={styles.tacticItem}>
                        <div className={styles.tacticRank}>{s.priority}</div>
                        <div className={styles.tacticContent}>
                          <div className={styles.tacticTitleRow}>
                            <div className={styles.tacticTitle}>{s.tactic}</div>
                            <div className={styles.tacticDeltaBadge}>{s.win_prob_change}</div>
                          </div>
                          <div className={styles.tacticMeta}>
                            <span className={styles.tacticMetaLabel}>근거</span>
                            <span className={styles.tacticMetaText}>{s.reason}</span>
                          </div>
                          <div className={styles.tacticMeta}>
                            <span className={styles.tacticMetaLabel}>기대효과</span>
                            <span className={styles.tacticMetaText}>{s.expected_effect}</span>
                          </div>
                          {relatedScenario && (
                            <div className={styles.tacticScenario}>
                              <div className={styles.tacticScenarioTitle}>관련 시나리오</div>
                              <div className={styles.tacticScenarioDesc}>
                                {relatedScenario.description}
                              </div>
                              <div className={styles.tacticScenarioMetrics}>
                                <span>승</span> {fmtPct(relatedScenario.before.win)} →{' '}
                                {fmtPct(relatedScenario.after.win)}
                                <span className={styles.tacticScenarioDelta}>
                                  {relatedScenario.win_change >= 0 ? '+' : ''}
                                  {pct(relatedScenario.win_change).toFixed(1)}%p
                                </span>
                              </div>
                              <div className={styles.tacticScenarioNote}>
                                {relatedScenario.recommendation}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className={styles.detailHint}>전술 제안을 준비 중입니다.</div>
              )}
            </div>

            <div className={styles.detailCard}>
              <div className={styles.detailHeader}>
                <div className={styles.detailTitle}>전술 시나리오</div>
                {simUpdating && <span className={styles.detailUpdate}>업데이트 중</span>}
              </div>
              {simPending ? (
                <div className={styles.detailHint}>시나리오 계산 중...</div>
              ) : scenarios.length ? (
                <div className={styles.scenarioList}>
                  {scenarios.slice(0, 3).map((sc) => (
                    <div key={sc.scenario} className={styles.scenarioItem}>
                      <div className={styles.scenarioTitleRow}>
                        <div className={styles.scenarioTitle}>{sc.scenario}</div>
                        <div className={styles.scenarioDeltaBadge}>
                          {sc.win_change >= 0 ? '+' : ''}
                          {pct(sc.win_change).toFixed(1)}%p
                        </div>
                      </div>
                      <div className={styles.scenarioDesc}>{sc.description}</div>
                      <div className={styles.scenarioMetrics}>
                        <div>
                          <span>승</span> {fmtPct(sc.before.win)} → {fmtPct(sc.after.win)}
                        </div>
                        <div>
                          <span>무</span> {fmtPct(sc.before.draw)} → {fmtPct(sc.after.draw)}
                        </div>
                        <div>
                          <span>패</span> {fmtPct(sc.before.lose)} → {fmtPct(sc.after.lose)}
                        </div>
                      </div>
                      <div className={styles.scenarioRecommendation}>{sc.recommendation}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className={styles.detailHint}>시나리오 데이터가 없습니다.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
