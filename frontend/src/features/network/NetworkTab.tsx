'use client';

import { useState } from 'react';
import PassNetwork from '@/components/PassNetwork';
import { useNetworkGraph } from '@/hooks/useNetworkGraph';
import { useTeamVAEP } from '@/hooks/useTeamVAEP';
import type { Hub } from '@/types';
import styles from '@/app/page.module.css';

type NetworkSubTab = 'network' | 'vaep' | 'hubs';

interface Props {
  teamId: number | null;
  hubs: Hub[];
}

const sf = (val: number, d: number = 1) => (Number.isFinite(val) ? val.toFixed(d) : (0).toFixed(d));

// 네트워크 탭 - 패스 네트워크 / VAEP 공헌도 / 빌드업 허브 (3 서브탭)
export default function NetworkTab({ teamId, hubs }: Props) {
  const [subTab, setSubTab] = useState<NetworkSubTab>('network');
  const { graph } = useNetworkGraph(teamId);
  const { vaep } = useTeamVAEP(teamId);

  return (
    <div className={styles.networkScroll}>
      <div className={styles.simSubTabs}>
        <button
          onClick={() => setSubTab('network')}
          className={`${styles.simSubTab} ${subTab === 'network' ? styles.simSubTabActive : ''}`}
        >
          네트워크
        </button>
        <button
          onClick={() => setSubTab('vaep')}
          className={`${styles.simSubTab} ${subTab === 'vaep' ? styles.simSubTabActive : ''}`}
        >
          공헌도
        </button>
        <button
          onClick={() => setSubTab('hubs')}
          className={`${styles.simSubTab} ${subTab === 'hubs' ? styles.simSubTabActive : ''}`}
        >
          허브
        </button>
      </div>

      {subTab === 'network' && (
        <div className={styles.networkChart}>
          {graph ? (
            <PassNetwork nodes={graph.nodes} edges={graph.edges} />
          ) : (
            <div className={`card ${styles.networkPlaceholder}`}>네트워크 로딩 중...</div>
          )}
        </div>
      )}

      {subTab === 'vaep' && (
        <div className={styles.vaepSection}>
          <div className={`card ${styles.vaepCard}`}>
            {!vaep ? (
              <div className={styles.panelPlaceholder}>VAEP 분석 불러오는 중...</div>
            ) : (
              <>
                <div className={`card-title ${styles.vaepTitle}`}>
                  선수 공헌도 (VAEP)
                  <span className={styles.vaepBadge}>{vaep.methodology}</span>
                </div>

                <p className={styles.vaepSummary}>
                  총 팀 VAEP: <strong>{sf(vaep.team_total_vaep)}</strong>점
                </p>

                <div className={styles.vaepGrid}>
                  <div className={styles.vaepListCard}>
                    <h4 className={styles.vaepListTitlePrimary}>전체 TOP 5</h4>
                    {vaep.top_players.slice(0, 5).map((p, i) => (
                      <div key={p.player_id} className={styles.vaepItemPrimary}>
                        <span className={styles.vaepPlayerName}>
                          <span
                            style={{
                              display: 'inline-block',
                              width: 18,
                              height: 18,
                              borderRadius: '50%',
                              background:
                                i === 0
                                  ? '#f59e0b'
                                  : i === 1
                                    ? '#94a3b8'
                                    : i === 2
                                      ? '#b45309'
                                      : '#e2e8f0',
                              color: i < 3 ? 'white' : '#64748b',
                              textAlign: 'center',
                              lineHeight: '18px',
                              fontSize: 10,
                              marginRight: 6,
                              fontWeight: 700,
                            }}
                          >
                            {i + 1}
                          </span>
                          {p.player_name}
                        </span>
                        <span className={styles.vaepScorePrimary}>{sf(p.total_vaep)}</span>
                      </div>
                    ))}
                  </div>

                  <div className={styles.vaepListCard}>
                    <h4 className={styles.vaepListTitleOff}>공격 TOP 5</h4>
                    {vaep.top_offensive.slice(0, 5).map((p) => (
                      <div key={p.player_id} className={styles.vaepItemOff}>
                        <span className={styles.vaepPlayerName}>{p.player_name}</span>
                        <span className={styles.vaepScoreOff}>{sf(p.offensive_vaep)}</span>
                      </div>
                    ))}
                  </div>

                  <div className={styles.vaepListCard}>
                    <h4 className={styles.vaepListTitleDef}>수비 TOP 5</h4>
                    {vaep.top_defensive.slice(0, 5).map((p) => (
                      <div key={p.player_id} className={styles.vaepItemDef}>
                        <span className={styles.vaepPlayerName}>{p.player_name}</span>
                        <span className={styles.vaepScoreDef}>{sf(p.defensive_vaep)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {subTab === 'hubs' && (
        <div className="pattern-grid">
          {hubs.map((hub) => (
            <div key={hub.player_id} className="card">
              <div className="hub-card">
                <div className="hub-avatar">{hub.position}</div>
                <div className={`hub-info ${styles.hubInfo}`}>
                  <h4>{hub.player_name}</h4>
                  <p>
                    {hub.main_position} • 허브 점수 {sf(hub.hub_score * 100, 0)}
                  </p>
                </div>
              </div>
              <div className={styles.hubStatsGrid}>
                <div className={`${styles.hubStat} ${styles.hubStatReceive}`}>
                  <div className={styles.hubStatValueReceive}>{hub.passes_received}</div>
                  <div className={styles.hubStatLabel}>패스 수신</div>
                </div>
                <div className={`${styles.hubStat} ${styles.hubStatPass}`}>
                  <div className={styles.hubStatValuePass}>{hub.passes_made}</div>
                  <div className={styles.hubStatLabel}>패스 시도</div>
                </div>
              </div>
              <p className={styles.hubImpact}>
                {hub.disruption_impact?.description || '압박 타겟'}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
