'use client';

import { useState, useEffect } from 'react';
import {
  getTeamPatterns,
  getTeamSetpieces,
  getTeamNetwork,
  getTeamsOverview,
  runPreMatchSimulation,
  getTeamVAEP,
  getTeamPhases,
  getPhaseReplay,
  matchList,
  matchChances,
  getTeamAnalysis,
  getNetworkGraph,
  MatchResult,
  ChanceAnalysis,
  TeamAnalysis,
  VAEPSummary,
} from '@/lib/api';
import { Pattern, SetPieceRoutine, Hub, ReplayEvent } from '@/types';
import PitchReplay from '@/components/PitchReplay';
import KeyMomentPitch from '@/components/KeyMomentPitch';
import SetpiecePitch from '@/components/SetpiecePitch';
import PassNetwork from '@/components/PassNetwork';

interface TeamStanding {
  team_id: number;
  team_name: string;
  rank: number;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  goals_for: number;
  goals_against: number;
  goal_diff: number;
  points: number;
  form: string[];
}

type Tab = 'overview' | 'patterns' | 'setpieces' | 'network' | 'simulation';

export default function Home() {
  const [standings, setStandings] = useState<TeamStanding[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<TeamStanding | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [loading, setLoading] = useState(true);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [setpieces, setSetpieces] = useState<SetPieceRoutine[]>([]);
  const [hubs, setHubs] = useState<Hub[]>([]);

  // Simulation state
  const [opponent, setOpponent] = useState<TeamStanding | null>(null);
  const [simLoading, setSimLoading] = useState(false);
  const [simResult, setSimResult] = useState<{
    base_prediction: { win: number; draw: number; lose: number };
    optimal_prediction: { win: number; draw: number; lose: number };
    win_improvement: number;
    tactical_suggestions: Array<{ priority: number; tactic: string; reason: string; expected_effect: string; win_prob_change: string }>;
  } | null>(null);

  // Pitch replay state
  interface Phase {
    phase_id: number;
    length: number;
    duration: number;
    has_shot: boolean;
    passes: number;
    start_zone: string;
    event_sequence: string;
  }
  const [phases, setPhases] = useState<Phase[]>([]);
  const [selectedPhase, setSelectedPhase] = useState<number | null>(null);
  const [replayEvents, setReplayEvents] = useState<ReplayEvent[]>([]);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [replayLoading, setReplayLoading] = useState(false);
  const [showReplayModal, setShowReplayModal] = useState(false);
  const [setpieceIndex, setSetpieceIndex] = useState(0);

  // Match analysis state
  const [recentMatches, setRecentMatches] = useState<MatchResult[]>([]);
  const [selectedMatch, setSelectedMatch] = useState<number | null>(null);
  const [chanceAnalysis, setChanceAnalysis] = useState<ChanceAnalysis | null>(null);
  const [chanceLoading, setChanceLoading] = useState(false);

  // Team AI analysis state
  const [teamAnalysis, setTeamAnalysis] = useState<TeamAnalysis | null>(null);

  // Network graph state
  interface NetworkData {
    nodes: Array<{ id: string; name: string; position: string; hub_score: number; passes_total: number }>;
    edges: Array<{ source: string; target: string; weight: number }>;
  }
  const [networkGraph, setNetworkGraph] = useState<NetworkData | null>(null);

  // VAEP state
  const [vaepData, setVaepData] = useState<VAEPSummary | null>(null);

  useEffect(() => {
    loadStandings();
  }, []);

  useEffect(() => {
    if (selectedTeam) {
      loadAnalysis();
    }
  }, [selectedTeam]);

  async function loadStandings() {
    try {
      const standingsData = await getTeamsOverview();
      setStandings(standingsData.standings);
    } catch (err) {
      console.error('Failed to load standings:', err);
    } finally {
      setLoading(false);
    }
  }

  async function loadAnalysis() {
    if (!selectedTeam) return;
    setAnalysisLoading(true);
    try {
      const [p, s, n, ph, matchesData] = await Promise.all([
        getTeamPatterns(selectedTeam.team_id, 100, 5),  // 전체 경기
        getTeamSetpieces(selectedTeam.team_id, 100),    // 전체 경기
        getTeamNetwork(selectedTeam.team_id, 100, 3),   // 전체 경기
        getTeamPhases(selectedTeam.team_id, 100),       // 전체 경기
        matchList(selectedTeam.team_id),
      ]);
      setPatterns(p.patterns);
      setSetpieces(s.routines);
      setHubs(n.hubs);
      setPhases(ph.phases);
      setSelectedPhase(null);
      setReplayEvents([]);
      setRecentMatches(matchesData.matches);
      setChanceAnalysis(null);

      // 팀 분석 로드 (비동기)
      getTeamAnalysis(selectedTeam.team_id).then(setTeamAnalysis).catch(console.error);

      // 네트워크 그래프 로드 (비동기)
      getNetworkGraph(selectedTeam.team_id, 100).then(data => {
        setNetworkGraph(data.graph);
      }).catch(console.error);

      // VAEP 분석 로드 (비동기)
      getTeamVAEP(selectedTeam.team_id).then(setVaepData).catch(console.error);
    } catch (err) {
      console.error('Failed to load analysis:', err);
    } finally {
      setAnalysisLoading(false);
    }
  }

  async function loadPhaseReplay(phaseId: number) {
    if (!selectedTeam) return;
    setReplayLoading(true);
    setIsPlaying(false);
    try {
      const data = await getPhaseReplay(selectedTeam.team_id, phaseId, 5);
      setReplayEvents(data.events);
      setSelectedPhase(phaseId);
    } catch (err) {
      console.error('Failed to load replay:', err);
    } finally {
      setReplayLoading(false);
    }
  }

  async function loadChanceAnalysis(gameId: number) {
    setChanceLoading(true);
    setSelectedMatch(gameId);
    try {
      const data = await matchChances(gameId);
      setChanceAnalysis(data);
    } catch (err) {
      console.error('Failed to load chance analysis:', err);
    } finally {
      setChanceLoading(false);
    }
  }

  const getRankClass = (rank: number, total: number) => {
    if (rank === 1) return 'rank-1';
    if (rank === 2) return 'rank-2';
    if (rank === 3) return 'rank-3';
    if (rank <= 4) return 'rank-acl';
    if (rank >= total - 2) return 'rank-down';
    return 'rank-normal';
  };

  // 팀 로고 파일명 매핑
  const getTeamLogo = (teamName: string) => {
    const logoMap: Record<string, string> = {
      '울산 HD FC': '울산 HD FC.png',
      '전북 현대 모터스': '전북 현대 모터스.png',
      '광주FC': '광주 FC.png',
      '인천 유나이티드': '인천 유나이티드.png',
      '강원FC': '강원 FC.png',
      '대구FC': '대구 FC.png',
      '수원FC': '수원 FC.png',
      '포항 스틸러스': '포항 스틸러스.png',
      '김천 상무 프로축구단': '김천상무프로축구단.png',
      '제주SK FC': '제주 SK FC.png',
      'FC서울': 'FC 서울.png',
      '대전 하나 시티즌': '대전 하나 시티즌.png',
    };
    // 다양한 이름 변형 처리
    for (const [key, value] of Object.entries(logoMap)) {
      if (teamName.includes(key.replace(/\s/g, '')) ||
        teamName.replace(/\s/g, '').includes(key.replace(/\s/g, ''))) {
        return `/logos/${value}`;
      }
    }
    // 직접 매칭 시도
    return `/logos/${teamName}.png`;
  };

  const tabs = [
    { id: 'overview', label: '분석 개요' },
    { id: 'patterns', label: '공격 패턴' },
    { id: 'setpieces', label: '세트피스' },
    { id: 'network', label: '허브 분석' },
    { id: 'simulation', label: '프리매치' },
  ];

  async function runSimulation() {
    if (!selectedTeam || !opponent) return;
    setSimLoading(true);
    try {
      const result = await runPreMatchSimulation(selectedTeam.team_id, opponent.team_id, 5);
      setSimResult(result);
    } catch (err) {
      console.error('Simulation failed:', err);
    } finally {
      setSimLoading(false);
    }
  }

  return (
    <div className="layout">
      {/* 사이드바 - 순위표 */}
      <aside className="sidebar">
        <div className="logo">
          <img
            src="/logos/K 리그.png"
            alt="K League"
            className="kleague-logo"
          />
          <div>
            <div className="logo-text">K LEAGUE</div>
            <div className="logo-sub">Matchday Scout</div>
          </div>
        </div>

        <div className="sidebar-title">K리그 1 순위</div>

        {loading ? (
          <div className="loading">
            <div className="spinner" />
          </div>
        ) : (
          <div className="team-list">
            {standings.map((team) => (
              <div
                key={team.team_id}
                className={`team-row ${selectedTeam?.team_id === team.team_id ? 'active' : ''}`}
                onClick={() => setSelectedTeam(team)}
              >
                <span className={`rank ${getRankClass(team.rank, standings.length)}`}>
                  {team.rank}
                </span>
                <img
                  src={getTeamLogo(team.team_name)}
                  alt={team.team_name}
                  className="team-logo"
                  onError={(e) => { e.currentTarget.style.display = 'none'; }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="team-name">{team.team_name}</div>
                  <div className="form-badges">
                    {team.form.map((f, i) => (
                      <span key={i} className={`form-badge form-${f.toLowerCase()}`}>{f}</span>
                    ))}
                  </div>
                </div>
                <span className="points">{team.points}</span>
              </div>
            ))}
          </div>
        )}
      </aside>

      {/* 메인 콘텐츠 */}
      <main className="main-content">
        {!selectedTeam ? (
          <div className="hero-section">
            <div className="hero-intro">
              <span className="hero-chip">K리그-서울시립대 공개 AI 경진대회</span>
              <h1 className="hero-title">
                경기 전,<br />
                <span className="gradient-text">승부는 이미 시작된다</span>
              </h1>
              <p className="hero-desc">
                579,307건의 K리그 이벤트 데이터를 AI가 분석하여<br />
                상대팀 공격 패턴, 세트피스 루틴, 핵심 선수를 파악합니다.
              </p>
            </div>

            <div className="feature-grid">
              <div className="feature-card">
                <div className="feature-icon">01</div>
                <h3>공격 패턴 분석</h3>
                <p>상대팀이 득점으로 연결하는 주요 공격 루트를 시각화합니다.</p>
              </div>
              <div className="feature-card">
                <div className="feature-icon">02</div>
                <h3>세트피스 인텔리전스</h3>
                <p>코너킥, 프리킥 시 상대팀의 주요 타겟 존과 수비 제안을 제공합니다.</p>
              </div>
              <div className="feature-card">
                <div className="feature-icon">03</div>
                <h3>빌드업 허브 탐지</h3>
                <p>상대 공격의 핵심 연결고리를 찾아 압박 포인트를 제안합니다.</p>
              </div>
              <div className="feature-card">
                <div className="feature-icon">04</div>
                <h3>AI 시뮬레이션</h3>
                <p>전술 조합에 따른 승률 변화를 예측하고 최적의 전략을 추천합니다.</p>
              </div>
            </div>

            <div className="hero-action">
              <p>좌측에서 분석할 팀을 선택하세요</p>
              <div className="quick-stats">
                <span><strong>12</strong> 팀</span>
                <span><strong>198</strong> 경기</span>
                <span><strong>446</strong> 선수</span>
              </div>
            </div>
          </div>
        ) : analysisLoading ? (
          <div className="loading">
            <div className="spinner" />
            <p style={{ marginTop: 16, color: '#64748b' }}>{selectedTeam.team_name} 분석 중...</p>
          </div>
        ) : (
          <>
            <div className="team-header">
              <img
                src={getTeamLogo(selectedTeam.team_name)}
                alt={selectedTeam.team_name}
                className="team-header-logo"
                onError={(e) => { e.currentTarget.style.display = 'none'; }}
              />
              <div className="team-header-info">
                <h1>{selectedTeam.team_name}</h1>
                <p>
                  {selectedTeam.rank}위 • {selectedTeam.points}점 • {selectedTeam.wins}승 {selectedTeam.draws}무 {selectedTeam.losses}패
                </p>
              </div>
            </div>

            <div className="tabs">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  className={`tab ${activeTab === tab.id ? 'active' : ''}`}
                  onClick={() => setActiveTab(tab.id as Tab)}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {activeTab === 'overview' && (
              <div style={{ maxHeight: 'calc(100vh - 200px)', overflowY: 'auto', paddingRight: 8 }}>
                <div className="stats-grid">
                  <div className="stat-card">
                    <div className="stat-value red">{patterns.length}</div>
                    <div className="stat-label">공격 패턴</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-value blue">{setpieces.length}</div>
                    <div className="stat-label">세트피스</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-value green">{hubs.length}</div>
                    <div className="stat-label">빌드업 허브</div>
                  </div>
                </div>

                {patterns[0] && (
                  <div className="card">
                    <div className="card-title">🎯 가장 위험한 패턴</div>
                    <div className="pattern-grid" style={{ gridTemplateColumns: '1fr' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
                        <div>
                          <div className="pattern-stat-value" style={{ color: '#e31837', fontSize: 24 }}>
                            {(patterns[0].shot_conversion_rate * 100).toFixed(1)}%
                          </div>
                          <div className="pattern-stat-label">슈팅 전환율</div>
                        </div>
                        <div>
                          <div className="pattern-stat-value">{patterns[0].frequency}</div>
                          <div className="pattern-stat-label">발생 횟수</div>
                        </div>
                        <div>
                          <div className="pattern-stat-value">{patterns[0].avg_passes.toFixed(1)}</div>
                          <div className="pattern-stat-label">평균 패스</div>
                        </div>
                        <div>
                          <div className="pattern-stat-value">{patterns[0].avg_duration.toFixed(0)}초</div>
                          <div className="pattern-stat-label">평균 시간</div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {hubs[0] && (
                  <div className="card">
                    <div className="card-title">⚡ 최우선 압박 타겟</div>
                    <div className="hub-card">
                      <div className="hub-avatar">{hubs[0].position}</div>
                      <div className="hub-info">
                        <h4>{hubs[0].player_name}</h4>
                        <p>허브 점수 {(hubs[0].hub_score * 100).toFixed(0)} • 패스 {hubs[0].passes_made}회</p>
                      </div>
                    </div>
                  </div>
                )}

                {/* 팀 AI 분석 */}
                {teamAnalysis && (
                  <div className="card" style={{ marginTop: 16, border: '1px solid #bfdbfe', background: 'linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)' }}>
                    <div className="card-title" style={{ color: '#1e40af', display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 18 }}>🤖</span>
                      AI 팀 분석
                      <span style={{
                        marginLeft: 'auto',
                        background: teamAnalysis.overall_score >= 70 ? '#16a34a' : teamAnalysis.overall_score >= 50 ? '#f59e0b' : '#dc2626',
                        color: 'white',
                        padding: '4px 12px',
                        borderRadius: 12,
                        fontSize: 14,
                        fontWeight: 700
                      }}>
                        {teamAnalysis.overall_score}점
                      </span>
                    </div>

                    <p style={{ fontSize: 14, color: '#1e40af', marginBottom: 16, fontStyle: 'italic' }}>
                      📊 {teamAnalysis.summary}
                    </p>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                      {/* 강점 */}
                      <div style={{ background: 'rgba(22, 163, 74, 0.1)', borderRadius: 12, padding: 16 }}>
                        <h4 style={{ color: '#16a34a', marginBottom: 12, fontSize: 14, fontWeight: 700 }}>💪 강점</h4>
                        {teamAnalysis.strengths.length > 0 ? teamAnalysis.strengths.map((s, i) => (
                          <div key={i} style={{ marginBottom: 10 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontWeight: 600, color: '#15803d', fontSize: 13 }}>{s.title}</span>
                              <span style={{
                                background: '#16a34a',
                                color: 'white',
                                padding: '2px 8px',
                                borderRadius: 8,
                                fontSize: 11,
                                fontWeight: 600
                              }}>{s.score}</span>
                            </div>
                            <p style={{ fontSize: 12, color: '#166534', marginTop: 4 }}>{s.description}</p>
                          </div>
                        )) : <p style={{ fontSize: 12, color: '#64748b' }}>분석 중...</p>}
                      </div>

                      {/* 약점 */}
                      <div style={{ background: 'rgba(239, 68, 68, 0.1)', borderRadius: 12, padding: 16 }}>
                        <h4 style={{ color: '#dc2626', marginBottom: 12, fontSize: 14, fontWeight: 700 }}>⚠️ 개선 필요</h4>
                        {teamAnalysis.weaknesses.length > 0 ? teamAnalysis.weaknesses.map((w, i) => (
                          <div key={i} style={{ marginBottom: 10 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontWeight: 600, color: '#b91c1c', fontSize: 13 }}>{w.title}</span>
                              <span style={{
                                background: '#dc2626',
                                color: 'white',
                                padding: '2px 8px',
                                borderRadius: 8,
                                fontSize: 11,
                                fontWeight: 600
                              }}>{w.score}</span>
                            </div>
                            <p style={{ fontSize: 12, color: '#991b1b', marginTop: 4 }}>{w.description}</p>
                          </div>
                        )) : <p style={{ fontSize: 12, color: '#64748b' }}>약점 없음 👍</p>}
                      </div>
                    </div>

                    {/* 인사이트 */}
                    {teamAnalysis.insights.length > 0 && (
                      <div style={{ marginTop: 16, padding: 12, background: 'rgba(59, 130, 246, 0.1)', borderRadius: 8 }}>
                        {teamAnalysis.insights.map((insight, i) => (
                          <div key={i} style={{ fontSize: 13, color: '#1e40af', marginBottom: i < teamAnalysis.insights.length - 1 ? 6 : 0 }}>
                            {insight}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* VAEP 선수 공헌도 랭킹 */}
                {vaepData && (
                  <div className="card" style={{ marginTop: 16, border: '1px solid #a5b4fc', background: 'linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%)' }}>
                    <div className="card-title" style={{ color: '#4338ca', display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                      <span style={{ fontSize: 18 }}>📊</span>
                      선수 공헌도 (VAEP)
                      <span style={{
                        marginLeft: 'auto',
                        fontSize: 11,
                        color: '#6366f1',
                        background: 'rgba(99, 102, 241, 0.15)',
                        padding: '3px 8px',
                        borderRadius: 6
                      }}>
                        {vaepData.methodology}
                      </span>
                    </div>

                    <p style={{ fontSize: 12, color: '#4338ca', marginBottom: 16, fontStyle: 'italic' }}>
                      총 팀 VAEP: <strong>{vaepData.team_total_vaep.toFixed(1)}</strong>점
                    </p>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                      {/* 전체 상위 5 */}
                      <div style={{ background: 'white', borderRadius: 10, padding: 12 }}>
                        <h4 style={{ color: '#4338ca', marginBottom: 10, fontSize: 13, fontWeight: 700 }}>🏆 전체 TOP 5</h4>
                        {vaepData.top_players.slice(0, 5).map((p, i) => (
                          <div key={p.player_id} style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            padding: '6px 0',
                            borderBottom: i < 4 ? '1px solid #e0e7ff' : 'none'
                          }}>
                            <span style={{ fontSize: 12, color: '#1e293b' }}>
                              <span style={{
                                display: 'inline-block',
                                width: 18,
                                height: 18,
                                borderRadius: '50%',
                                background: i === 0 ? '#f59e0b' : i === 1 ? '#94a3b8' : i === 2 ? '#b45309' : '#e2e8f0',
                                color: i < 3 ? 'white' : '#64748b',
                                textAlign: 'center',
                                lineHeight: '18px',
                                fontSize: 10,
                                marginRight: 6,
                                fontWeight: 700
                              }}>
                                {i + 1}
                              </span>
                              {p.player_name}
                            </span>
                            <span style={{
                              fontWeight: 700,
                              color: '#4338ca',
                              fontSize: 12
                            }}>
                              {p.total_vaep.toFixed(1)}
                            </span>
                          </div>
                        ))}
                      </div>

                      {/* 공격 상위 5 */}
                      <div style={{ background: 'white', borderRadius: 10, padding: 12 }}>
                        <h4 style={{ color: '#dc2626', marginBottom: 10, fontSize: 13, fontWeight: 700 }}>⚽ 공격 TOP 5</h4>
                        {vaepData.top_offensive.slice(0, 5).map((p, i) => (
                          <div key={p.player_id} style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            padding: '6px 0',
                            borderBottom: i < 4 ? '1px solid #fecaca' : 'none'
                          }}>
                            <span style={{ fontSize: 12, color: '#1e293b' }}>{p.player_name}</span>
                            <span style={{ fontWeight: 700, color: '#dc2626', fontSize: 12 }}>
                              {p.offensive_vaep.toFixed(1)}
                            </span>
                          </div>
                        ))}
                      </div>

                      {/* 수비 상위 5 */}
                      <div style={{ background: 'white', borderRadius: 10, padding: 12 }}>
                        <h4 style={{ color: '#059669', marginBottom: 10, fontSize: 13, fontWeight: 700 }}>🛡️ 수비 TOP 5</h4>
                        {vaepData.top_defensive.slice(0, 5).map((p, i) => (
                          <div key={p.player_id} style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            padding: '6px 0',
                            borderBottom: i < 4 ? '1px solid #a7f3d0' : 'none'
                          }}>
                            <span style={{ fontSize: 12, color: '#1e293b' }}>{p.player_name}</span>
                            <span style={{ fontWeight: 700, color: '#059669', fontSize: 12 }}>
                              {p.defensive_vaep.toFixed(1)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'patterns' && (
              <div>
                {/* 피치 시각화 섹션 */}
                <div className="card" style={{ marginBottom: 20 }}>
                  <div className="card-title" style={{ color: '#3b82f6', marginBottom: 16 }}>
                    ⚽ 경기 상황 리플레이
                  </div>

                  {/* Phase 선택 - 버튼 스타일 */}
                  <div style={{ marginBottom: 20 }}>
                    <p style={{ color: '#c9d1d9', fontSize: 14, marginBottom: 12, fontWeight: 500 }}>
                      공격 Phase 선택:
                    </p>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
                      {phases.slice(0, 10).map((ph, idx) => (
                        <button
                          key={ph.phase_id}
                          onClick={() => loadPhaseReplay(ph.phase_id)}
                          style={{
                            padding: '12px 20px',
                            background: selectedPhase === ph.phase_id
                              ? 'linear-gradient(135deg, #3b82f6, #2563eb)'
                              : 'rgba(30, 41, 59, 0.8)',
                            border: selectedPhase === ph.phase_id
                              ? '2px solid #60a5fa'
                              : '1px solid #374151',
                            borderRadius: 10,
                            cursor: 'pointer',
                            color: selectedPhase === ph.phase_id ? 'white' : '#cbd5e1',
                            fontWeight: selectedPhase === ph.phase_id ? 600 : 400,
                            boxShadow: selectedPhase === ph.phase_id
                              ? '0 4px 12px rgba(59, 130, 246, 0.4)'
                              : 'none',
                            transition: 'all 0.2s ease',
                          }}
                        >
                          <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
                            Phase {idx + 1} ⚽
                          </div>
                          <div style={{ fontSize: 12, opacity: 0.9 }}>
                            패스 {ph.passes}회 · {Math.round(ph.duration)}초
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* 피치 리플레이 + 패턴 가로 배치 */}
                  <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
                    {/* 피치 리플레이 */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      {replayLoading ? (
                        <div style={{ textAlign: 'center', padding: 20, color: '#60a5fa' }}>⏳ 로딩 중...</div>
                      ) : replayEvents.length > 0 ? (
                        <PitchReplay
                          events={replayEvents}
                          isPlaying={isPlaying}
                          onPlayPause={() => setIsPlaying(!isPlaying)}
                          playbackSpeed={playbackSpeed}
                          onSpeedChange={setPlaybackSpeed}
                        />
                      ) : (
                        <div style={{
                          textAlign: 'center',
                          padding: 30,
                          background: 'rgba(30, 41, 59, 0.6)',
                          borderRadius: 10,
                          border: '2px dashed #374151',
                        }}>
                          <div style={{ fontSize: 24, marginBottom: 6 }}>🎬</div>
                          <p style={{ color: '#60a5fa', fontWeight: 500, fontSize: 13 }}>
                            위에서 Phase를 선택하세요
                          </p>
                        </div>
                      )}
                    </div>

                    {/* 패턴 통계 - 컴팩트 세로 배치 */}
                    <div style={{
                      width: 130,
                      flexShrink: 0,
                      background: 'linear-gradient(180deg, #f0fdf4, #dcfce7)',
                      borderRadius: 12,
                      padding: 12,
                      border: '1px solid #bbf7d0'
                    }}>
                      <div style={{
                        fontSize: 11,
                        fontWeight: 700,
                        color: '#16a34a',
                        marginBottom: 10,
                        textAlign: 'center'
                      }}>
                        📊 패턴 TOP 5
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {patterns.slice(0, 5).map((pattern, i) => (
                          <div key={pattern.cluster_id} style={{
                            padding: '6px 8px',
                            background: 'white',
                            borderRadius: 6,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
                          }}>
                            <span style={{
                              fontSize: 10,
                              color: '#64748b',
                              fontWeight: 600,
                              background: '#f1f5f9',
                              padding: '2px 5px',
                              borderRadius: 3
                            }}>
                              #{i + 1}
                            </span>
                            <span style={{ fontSize: 14, fontWeight: 700, color: '#16a34a' }}>
                              {(pattern.shot_conversion_rate * 100).toFixed(0)}%
                            </span>
                            <span style={{ fontSize: 9, color: '#94a3b8' }}>
                              {pattern.frequency}회
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'setpieces' && setpieces.length > 0 && (
              <div style={{ background: 'white', borderRadius: 12, padding: 20, border: '1px solid #e2e8f0' }}>
                {/* 상단 네비게이션 */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                  <button
                    onClick={() => setSetpieceIndex(Math.max(0, setpieceIndex - 1))}
                    disabled={setpieceIndex === 0}
                    style={{
                      width: 40, height: 40, borderRadius: 8, border: 'none',
                      background: setpieceIndex === 0 ? '#f1f5f9' : '#3b82f6',
                      color: setpieceIndex === 0 ? '#94a3b8' : 'white',
                      cursor: setpieceIndex === 0 ? 'not-allowed' : 'pointer',
                      fontSize: 18, fontWeight: 700
                    }}
                  >
                    ←
                  </button>

                  {/* 현재 세트피스 정보 */}
                  <div style={{ textAlign: 'center' }}>
                    <span style={{
                      fontSize: 12, fontWeight: 600,
                      color: setpieces[setpieceIndex]?.type.includes('Corner') ? '#f59e0b' : '#3b82f6',
                      background: setpieces[setpieceIndex]?.type.includes('Corner') ? '#fef3c7' : '#dbeafe',
                      padding: '4px 12px', borderRadius: 6
                    }}>
                      {setpieces[setpieceIndex]?.type.includes('Corner') ? '코너킥' : '프리킥'}
                    </span>
                    <span style={{ marginLeft: 12, fontSize: 22, fontWeight: 700, color: '#16a34a' }}>
                      슈팅 전환율 {(setpieces[setpieceIndex]?.shot_rate * 100).toFixed(0)}%
                    </span>
                    <span style={{ marginLeft: 16, fontSize: 14, color: '#64748b' }}>
                      {setpieceIndex + 1} / {setpieces.length}
                    </span>
                  </div>

                  <button
                    onClick={() => setSetpieceIndex(Math.min(setpieces.length - 1, setpieceIndex + 1))}
                    disabled={setpieceIndex === setpieces.length - 1}
                    style={{
                      width: 40, height: 40, borderRadius: 8, border: 'none',
                      background: setpieceIndex === setpieces.length - 1 ? '#f1f5f9' : '#3b82f6',
                      color: setpieceIndex === setpieces.length - 1 ? '#94a3b8' : 'white',
                      cursor: setpieceIndex === setpieces.length - 1 ? 'not-allowed' : 'pointer',
                      fontSize: 18, fontWeight: 700
                    }}
                  >
                    →
                  </button>
                </div>

                {/* 피치 시각화 */}
                <div style={{ display: 'flex', justifyContent: 'center' }}>
                  <SetpiecePitch routine={setpieces[setpieceIndex]} />
                </div>

                {/* 하단 통계 */}
                <div style={{
                  display: 'flex',
                  justifyContent: 'center',
                  gap: 40,
                  marginTop: 16,
                  padding: '12px 0',
                  borderTop: '1px solid #e2e8f0'
                }}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 24, fontWeight: 700, color: '#1e293b' }}>{setpieces[setpieceIndex]?.frequency}</div>
                    <div style={{ fontSize: 12, color: '#64748b' }}>발생 횟수</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 24, fontWeight: 700, color: '#1e293b' }}>
                      {setpieces[setpieceIndex]?.swing_type === 'inswing' ? '인스윙' : '아웃스윙'}
                    </div>
                    <div style={{ fontSize: 12, color: '#64748b' }}>킥 타입</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 24, fontWeight: 700, color: '#1e293b' }}>
                      {(() => {
                        const zone = setpieces[setpieceIndex]?.primary_zone || '';
                        const zoneMap: Record<string, string> = {
                          'far_post': '먼 포스트',
                          'near_post': '가까운 포스트',
                          'center': '중앙',
                          'central': '중앙',
                          'penalty_spot': '페널티 스팟',
                          'six_yard': '6야드 박스',
                          'edge_box': '박스 경계',
                          'edge_of_box': '박스 경계',
                          'unknown': '미정',
                          'Unknown': '미정',
                          '': '미정'
                        };
                        return zoneMap[zone] || zone;
                      })()}
                    </div>
                    <div style={{ fontSize: 12, color: '#64748b' }}>타겟존</div>
                  </div>
                </div>

                {/* 수비 제안 */}
                <div style={{
                  marginTop: 12,
                  padding: 12,
                  background: 'rgba(239, 68, 68, 0.1)',
                  borderRadius: 8,
                  color: '#dc2626',
                  fontSize: 13
                }}>
                  💡 {setpieces[setpieceIndex]?.defense_suggestion}
                </div>
              </div>
            )}

            {activeTab === 'network' && (
              <div style={{ maxHeight: 'calc(100vh - 200px)', overflowY: 'auto', paddingRight: 8 }}>
                {/* 패스 네트워크 시각화 */}
                {networkGraph && (
                  <div style={{ marginBottom: 20 }}>
                    <PassNetwork
                      nodes={networkGraph.nodes}
                      edges={networkGraph.edges}
                    />
                  </div>
                )}

                {/* 허브 선수 카드 */}
                <div className="pattern-grid">
                  {hubs.map((hub) => (
                    <div key={hub.player_id} className="card">
                      <div className="hub-card">
                        <div className="hub-avatar">{hub.position}</div>
                        <div className="hub-info" style={{ flex: 1 }}>
                          <h4>{hub.player_name}</h4>
                          <p>{hub.main_position} • 허브 점수 {(hub.hub_score * 100).toFixed(0)}</p>
                        </div>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 16 }}>
                        <div style={{ textAlign: 'center', padding: 12, background: 'rgba(35,134,54,0.1)', borderRadius: 6 }}>
                          <div style={{ fontSize: 20, fontWeight: 700, color: '#238636' }}>{hub.passes_received}</div>
                          <div style={{ fontSize: 11, color: '#8b949e' }}>패스 수신</div>
                        </div>
                        <div style={{ textAlign: 'center', padding: 12, background: 'rgba(31,111,235,0.1)', borderRadius: 6 }}>
                          <div style={{ fontSize: 20, fontWeight: 700, color: '#1f6feb' }}>{hub.passes_made}</div>
                          <div style={{ fontSize: 11, color: '#8b949e' }}>패스 시도</div>
                        </div>
                      </div>
                      <p style={{ fontSize: 12, marginTop: 12, padding: 10, background: 'rgba(227,24,55,0.1)', borderRadius: 6, color: '#e31837' }}>
                        {hub.disruption_impact?.description || '압박 타겟'}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === 'simulation' && (
              <div style={{ padding: '0 4px' }}>
                {/* 1. 매치 리스트 뷰 (선택된 매치가 없을 때) */}
                {!selectedMatch && (
                  <div className="fade-in">
                    <div style={{ marginBottom: 20 }}>
                      <div style={{ fontSize: 18, fontWeight: 700, color: '#f59e0b', marginBottom: 6 }}>
                        🔍 경기 분석 - 놓친 찬스
                      </div>
                      <p style={{ fontSize: 14, color: '#64748b' }}>
                        분석할 경기를 선택하세요. 패배/무승부 경기에서 <strong style={{ color: '#22c55e' }}>승리할 수 있었던 기회</strong>를 찾아냅니다.
                      </p>
                    </div>

                    <div style={{ display: 'grid', gap: 12, maxHeight: 'calc(100vh - 280px)', overflowY: 'auto', paddingRight: 8 }}>
                      {recentMatches
                        .filter((match) => {
                          if (!selectedTeam) return true;
                          const teamId = selectedTeam.team_id;
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
                              style={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                padding: '20px 24px',
                                background: 'white',
                                border: '1px solid #e2e8f0',
                                borderLeft: `6px solid ${isDraw ? '#f59e0b' : '#ef4444'}`,
                                borderRadius: 12,
                                cursor: 'pointer',
                                textAlign: 'left',
                                transition: 'all 0.2s ease',
                                boxShadow: '0 2px 4px rgba(0,0,0,0.02)'
                              }}
                              onMouseOver={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
                              onMouseOut={(e) => e.currentTarget.style.transform = 'translateY(0)'}
                            >
                              <div>
                                <div style={{ fontSize: 13, color: '#94a3b8', marginBottom: 4 }}>{match.date}</div>
                                <div style={{ fontSize: 18, fontWeight: 700, color: '#1e293b' }}>
                                  {match.home_team} <span style={{ color: '#cbd5e1', margin: '0 8px' }}>vs</span> {match.away_team}
                                </div>
                              </div>
                              <div style={{ textAlign: 'right' }}>
                                <div style={{ fontSize: 24, fontWeight: 800, color: '#1e293b', letterSpacing: '-1px' }}>
                                  {match.score}
                                </div>
                                <div style={{
                                  fontSize: 12, fontWeight: 600,
                                  color: isDraw ? '#d97706' : '#dc2626'
                                }}>
                                  {match.result_text}
                                </div>
                              </div>
                            </button>
                          );
                        })}
                    </div>
                  </div>
                )}

                {/* 2. 상세 분석 뷰 (매치가 선택되었을 때) */}
                {selectedMatch && (
                  <div className="fade-in">
                    <button
                      onClick={() => {
                        setSelectedMatch(null);
                        setChanceAnalysis(null);
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        border: 'none',
                        background: 'transparent',
                        color: '#64748b',
                        fontSize: 14,
                        fontWeight: 600,
                        cursor: 'pointer',
                        padding: '8px 0',
                        marginBottom: 12
                      }}
                    >
                      <span>←</span> 뒤로가기
                    </button>

                    {chanceLoading ? (
                      <div style={{ padding: 60, textAlign: 'center', color: '#64748b' }}>
                        분석 중입니다...
                      </div>
                    ) : chanceAnalysis ? (
                      <div className="analysis-result">
                        <div className="card" style={{ padding: 24, border: '1px solid #bfdbfe', background: '#eff6ff' }}>
                          <h3 style={{ margin: '0 0 16px 0', color: '#1e3a8a', display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: 20 }}>💡</span>
                            AI 분석 리포트
                          </h3>
                          <div style={{ fontSize: 15, lineHeight: 1.6, color: '#1e40af' }}>
                            {chanceAnalysis.summary}
                          </div>
                        </div>

                        <div className="card" style={{ marginTop: 20, border: 'none', background: 'transparent', padding: 0 }}>
                          <h4 style={{ margin: '0 0 16px 4px', color: '#475569' }}>결정적 장면 재구성</h4>
                          <div style={{
                            display: 'grid',
                            gridTemplateColumns: chanceAnalysis.chances.length > 1 ? '1fr 1fr' : '1fr',
                            gap: 20
                          }}>
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
          </>
        )}
      </main>
    </div>
  );
}
