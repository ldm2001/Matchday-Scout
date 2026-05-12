// K리그 전술 분석 대시보드
'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Image from 'next/image';
import {
  teamPatterns,
  teamSetpieces,
  teamNetwork,
  teamsOverview,
  preMatch,
  teamVAEP,
  teamPhases,
  phaseReplay,
  matchList,
  matchChances,
  teamAnalysis,
  netGraph,
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
import VideoAnalysis from '@/components/VideoAnalysis';
import styles from './page.module.css';

// 팀 순위 정보 타입
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

// 탭 종류 정의
type Tab = 'overview' | 'patterns' | 'setpieces' | 'network' | 'simulation' | 'video';
const ANALYSIS_GAMES = 100;

// 시뮬레이션 결과 타입
type SimResult = {
  base_prediction: { win: number; draw: number; lose: number };
  optimal_prediction: { win: number; draw: number; lose: number };
  win_improvement: number;
  tactical_suggestions: Array<{ priority: number; tactic: string; reason: string; expected_effect: string; win_prob_change: string }>;
  scenarios?: Array<{
    scenario: string;
    description: string;
    before: { win: number; draw: number; lose: number };
    after: { win: number; draw: number; lose: number };
    win_change: number;
    recommendation: string;
  }>;
};

// 메인 컴포넌트 - 팀 선택, 분석 탭, 시뮬레이션 기능 제공
export default function Home() {
  const [standings, setStandings] = useState<TeamStanding[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<TeamStanding | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [loading, setLoading] = useState(true);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const analysisToken = useRef(0);
  const simToken = useRef(0);
  const simKeyRef = useRef<string | null>(null);
  const simDataRef = useRef<string | null>(null);
  const contentScrollRef = useRef<HTMLDivElement | null>(null);

  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [setpieces, setSetpieces] = useState<SetPieceRoutine[]>([]);
  const [hubs, setHubs] = useState<Hub[]>([]);

  // Simulation state
  const [opponent, setOpponent] = useState<TeamStanding | null>(null);
  const [simLoading, setSimLoading] = useState(false);
  const [simResult, setSimResult] = useState<SimResult | null>(null);
  const [simPulse, setSimPulse] = useState(false);
  const simCacheRef = useRef<Record<string, SimResult>>({});
  const opponentCacheRef = useRef<Record<number, number>>({});

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
  const [setpieceIndex, setSetpieceIndex] = useState(0);

  // Match analysis state
  const [recentMatches, setRecentMatches] = useState<MatchResult[]>([]);
  const [selectedMatch, setSelectedMatch] = useState<number | null>(null);
  const [chanceAnalysis, setChanceAnalysis] = useState<ChanceAnalysis | null>(null);
  const [chanceLoading, setChanceLoading] = useState(false);

  // Team AI analysis state
  const [analysis, setAnalysis] = useState<TeamAnalysis | null>(null);

  // Network graph state
  interface NetworkData {
    nodes: Array<{ id: string; name: string; position: string; hub_score: number; passes_total: number }>;
    edges: Array<{ source: string; target: string; weight: number }>;
  }
  const [networkGraph, setNetworkGraph] = useState<NetworkData | null>(null);

  // VAEP state
  const [vaepData, setVaepData] = useState<VAEPSummary | null>(null);

  // 팀 순위 초기 로딩
  const loadStandings = useCallback(async () => {
    try {
      const standingsData = await teamsOverview();
      setStandings(standingsData.standings);
    } catch (err) {
      console.error('Failed to load standings:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // 선택 팀 전체 분석 로더
  const loadAnalysis = useCallback(async () => {
    if (!selectedTeam) return;
    const token = analysisToken.current + 1;
    analysisToken.current = token;
    setAnalysisLoading(true);
    setPatterns([]);
    setSetpieces([]);
    setHubs([]);
    setPhases([]);
    setSelectedPhase(null);
    setReplayEvents([]);
    setRecentMatches([]);
    setChanceAnalysis(null);
    setAnalysis(null);
    setNetworkGraph(null);
    setVaepData(null);
    setSetpieceIndex(0);

    const teamId = selectedTeam.team_id;
    const loadStep = async <T,>(task: () => Promise<T>, apply: (data: T) => void) => {
      try {
        const data = await task();
        if (analysisToken.current !== token) return false;
        apply(data);
        return true;
      } catch (err) {
        if (analysisToken.current === token) console.error(err);
        return true;
      }
    };

    if (!(await loadStep(() => teamPatterns(teamId, ANALYSIS_GAMES, 5), (data) => {
      setPatterns(data.patterns);
    }))) return;

    if (!(await loadStep(() => teamSetpieces(teamId, ANALYSIS_GAMES), (data) => {
      setSetpieces(data.routines);
    }))) return;

    if (!(await loadStep(() => teamNetwork(teamId, ANALYSIS_GAMES, 3), (data) => {
      setHubs(data.hubs);
    }))) return;

    if (!(await loadStep(() => teamPhases(teamId, ANALYSIS_GAMES), (data) => {
      setPhases(data.phases);
    }))) return;

    if (!(await loadStep(() => matchList(teamId), (data) => {
      setRecentMatches(data.matches);
    }))) return;

    if (!(await loadStep(() => teamAnalysis(teamId, ANALYSIS_GAMES), (data) => {
      setAnalysis(data);
    }))) return;

    if (!(await loadStep(() => netGraph(teamId, ANALYSIS_GAMES), (data) => {
      setNetworkGraph(data.graph);
    }))) return;

    await loadStep(() => teamVAEP(teamId, ANALYSIS_GAMES), (data) => {
      setVaepData(data);
    });

    if (analysisToken.current === token) setAnalysisLoading(false);
  }, [selectedTeam]);

  useEffect(() => {
    loadStandings();
  }, [loadStandings]);

  useEffect(() => {
    if (selectedTeam) {
      loadAnalysis();
    }
  }, [selectedTeam, loadAnalysis]);

  useEffect(() => {
    if (!selectedTeam || standings.length === 0) {
      setOpponent(null);
      simKeyRef.current = null;
      return;
    }
    const cachedOpponentId = opponentCacheRef.current[selectedTeam.team_id];
    const cachedOpponent = standings.find((team) => team.team_id === cachedOpponentId);
    if (cachedOpponent && cachedOpponent.team_id !== selectedTeam.team_id) {
      setOpponent(cachedOpponent);
      simKeyRef.current = null;
      return;
    }
    const candidates = standings.filter((team) => team.team_id !== selectedTeam.team_id);
    if (candidates.length === 0) {
      setOpponent(null);
      simKeyRef.current = null;
      return;
    }
    const nextOpponent = candidates.reduce((closest, team) => {
      const closestDiff = Math.abs(closest.rank - selectedTeam.rank);
      const teamDiff = Math.abs(team.rank - selectedTeam.rank);
      return teamDiff < closestDiff ? team : closest;
    }, candidates[0]);
    setOpponent((prev) => (prev && prev.team_id === nextOpponent.team_id ? prev : nextOpponent));
    opponentCacheRef.current[selectedTeam.team_id] = nextOpponent.team_id;
    simKeyRef.current = null;
  }, [selectedTeam, standings]);

  useEffect(() => {
    if (!selectedTeam || !opponent) {
      setSimResult(null);
      simDataRef.current = null;
      return;
    }
    const key = `${selectedTeam.team_id}-${opponent.team_id}`;
    const cached = simCacheRef.current[key];
    if (cached) {
      setSimResult(cached);
      simDataRef.current = key;
    }
  }, [selectedTeam, opponent]);

  // 공격 Phase 리플레이 로더
  async function loadPhaseReplay(phaseId: number) {
    if (!selectedTeam) return;
    const token = analysisToken.current;
    const teamId = selectedTeam.team_id;
    setReplayLoading(true);
    setIsPlaying(false);
    try {
      const data = await phaseReplay(teamId, phaseId, ANALYSIS_GAMES);
      if (analysisToken.current !== token) return;
      setReplayEvents(data.events);
      setSelectedPhase(phaseId);
    } catch (err) {
      console.error('Failed to load replay:', err);
    } finally {
      setReplayLoading(false);
    }
  }

  // 놓친 찬스 분석 로더
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

  const rankClass = (rank: number, total: number) => {
    if (rank === 1) return 'rank-1';
    if (rank === 2) return 'rank-2';
    if (rank === 3) return 'rank-3';
    if (rank <= 4) return 'rank-acl';
    if (rank >= total - 2) return 'rank-down';
    return 'rank-normal';
  };

  // 팀 로고 파일명 매핑
  const teamLogo = (teamName: string) => {
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
    { id: 'video', label: '영상 분석' },
  ];

  const handleTabChange = useCallback((tab: Tab) => {
    if (tab === activeTab) return;
    const scroller = contentScrollRef.current;
    if (scroller) {
      scroller.scrollTo({ top: 0, behavior: 'smooth' });
    }
    window.requestAnimationFrame(() => {
      setActiveTab(tab);
    });
  }, [activeTab]);

  // 프리매치 시뮬레이션 실행
  const runSimulation = useCallback(async (ourTeam: TeamStanding, oppTeam: TeamStanding) => {
    if (!ourTeam || !oppTeam) return;
    const token = simToken.current + 1;
    simToken.current = token;
    const key = `${ourTeam.team_id}-${oppTeam.team_id}`;
    setSimLoading(true);
    try {
      const result = await preMatch(ourTeam.team_id, oppTeam.team_id, ANALYSIS_GAMES);
      if (simToken.current !== token) return;
      simCacheRef.current[key] = result;
      setSimResult(result);
      simDataRef.current = key;
    } catch (err) {
      console.error('Simulation failed:', err);
    } finally {
      if (simToken.current === token) setSimLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedTeam || !opponent || activeTab !== 'simulation') return;
    const key = `${selectedTeam.team_id}-${opponent.team_id}`;
    if (simKeyRef.current === key) return;
    simKeyRef.current = key;
    runSimulation(selectedTeam, opponent);
  }, [selectedTeam, opponent, activeTab, runSimulation]);

  // 상대팀 선택 + 캐시 갱신
  const handleOpponentSelect = (team: TeamStanding) => {
    setOpponent(team);
    if (selectedTeam) {
      opponentCacheRef.current[selectedTeam.team_id] = team.team_id;
    }
    simKeyRef.current = null;
  };

  const pct = (val: number) => {
    if (!Number.isFinite(val)) return 0;
    const p = Math.abs(val) <= 1 ? val * 100 : val;
    return Math.max(-100, Math.min(100, p));
  };
  const fmtPct = (val: number) => `${pct(val).toFixed(1)}%`;
  const sf = (val: number, d: number = 1) => Number.isFinite(val) ? val.toFixed(d) : (0).toFixed(d);
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

  const patternCount = analysisLoading && patterns.length === 0 ? '—' : patterns.length;
  const setpieceCount = analysisLoading && setpieces.length === 0 ? '—' : setpieces.length;
  const hubCount = analysisLoading && hubs.length === 0 ? '—' : hubs.length;
  const canRunSim = Boolean(selectedTeam && opponent);
  const simKey = selectedTeam && opponent ? `${selectedTeam.team_id}-${opponent.team_id}` : null;
  const simStale = Boolean(simResult && simKey && simDataRef.current !== simKey);
  const simPending = canRunSim && !simResult;
  const simUpdating = simLoading || simStale;

  useEffect(() => {
    if (!simKey) return;
    setSimPulse(true);
    const timer = setTimeout(() => setSimPulse(false), 600);
    return () => clearTimeout(timer);
  }, [simKey, simResult]);

  const renderProbBars = (prediction?: { win: number; draw: number; lose: number }) => {
    if (!prediction) {
      return (
        <div className={styles.probHint}>
          상대팀을 선택하면 예측이 표시됩니다.
        </div>
      );
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
            <div className={styles.probLabel} style={{ color: row.color }}>{row.label}</div>
            <div className={styles.probTrack}>
              <div
                className={styles.probFill}
                style={{
                  width: `${Math.min(Math.max(row.value, 0), 100)}%`,
                  background: row.color,
                }}
              />
            </div>
            <div className={styles.probValue}>
              {row.value.toFixed(1)}%
            </div>
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
    <div className="layout">
      {/* 사이드바 - 순위표 */}
      <aside className="sidebar">
        <div className="logo">
          <Image
            src="/logos/K 리그.png"
            alt="K League"
            className="kleague-logo"
            width={40}
            height={40}
            priority
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
                <span className={`rank ${rankClass(team.rank, standings.length)}`}>
                  {team.rank}
                </span>
                <Image
                  src={teamLogo(team.team_name)}
                  alt={team.team_name}
                  className="team-logo"
                  width={24}
                  height={24}
                  onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }}
                />
                <div className={styles.teamRowInfo}>
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
          <div className="content-scroll">
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
                  <p>상대 득점 루트를 한눈에 봅니다.</p>
                </div>
                <div className="feature-card">
                  <div className="feature-icon">02</div>
                  <h3>세트피스 인텔리전스</h3>
                  <p>세트피스 약점과 대응을 알려줍니다.</p>
                </div>
                <div className="feature-card">
                  <div className="feature-icon">03</div>
                  <h3>빌드업 허브 탐지</h3>
                  <p>빌드업 핵심을 찾아 압박 지점을 제시합니다.</p>
                </div>
                <div className="feature-card">
                  <div className="feature-icon">04</div>
                  <h3>AI 시뮬레이션</h3>
                  <p>전술 조합별 승률을 예측합니다.</p>
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
          </div>
        ) : (
          <>
            <div className="team-top">
              <div className="team-header">
                <Image
                  src={teamLogo(selectedTeam.team_name)}
                  alt={selectedTeam.team_name}
                  className="team-header-logo"
                  width={64}
                  height={64}
                  onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }}
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
                    onClick={() => handleTabChange(tab.id as Tab)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="content-scroll" ref={contentScrollRef}>
              {activeTab === 'overview' && (
                <div className={styles.overviewScroll}>
                  <div className="stats-grid">
                    <div className="stat-card">
                      <div className="stat-value red">{patternCount}</div>
                      <div className="stat-label">공격 패턴</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-value blue">{setpieceCount}</div>
                      <div className="stat-label">세트피스</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-value green">{hubCount}</div>
                      <div className="stat-label">빌드업 허브</div>
                    </div>
                  </div>

                  {patterns[0] && (
                    <div className="card">
                      <div className="card-title">가장 위험한 패턴</div>
                      <div className={`pattern-grid ${styles.patternGridSingle}`}>
                        <div className={styles.patternStatGrid}>
                          <div>
                            <div className={`pattern-stat-value ${styles.patternHighlight}`}>
                              {sf(patterns[0].shot_conversion_rate * 100)}%
                            </div>
                            <div className="pattern-stat-label">슈팅 전환율</div>
                          </div>
                          <div>
                            <div className="pattern-stat-value">{patterns[0].frequency}</div>
                            <div className="pattern-stat-label">발생 횟수</div>
                          </div>
                          <div>
                            <div className="pattern-stat-value">{sf(patterns[0].avg_passes)}</div>
                            <div className="pattern-stat-label">평균 패스</div>
                          </div>
                          <div>
                            <div className="pattern-stat-value">{sf(patterns[0].avg_duration, 0)}초</div>
                            <div className="pattern-stat-label">평균 시간</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {hubs[0] && (
                    <div className="card">
                      <div className="card-title">최우선 압박 타겟</div>
                      <div className="hub-card">
                        <div className="hub-avatar">{hubs[0].position}</div>
                        <div className="hub-info">
                          <h4>{hubs[0].player_name}</h4>
                          <p>허브 점수 {sf(hubs[0].hub_score * 100, 0)} • 패스 {hubs[0].passes_made}회</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* 팀 AI 분석 */}
                  <div className={styles.analysisSection}>
                    <div className={`card ${styles.teamAnalysisCard}`}>
                      {!analysis ? (
                        <div className={styles.panelPlaceholder}>
                          AI 팀 분석 불러오는 중...
                        </div>
                      ) : (
                        <>
                          <div className={`card-title ${styles.teamAnalysisTitle}`}>
                            AI 팀 분석
                            <span
                              className={styles.teamAnalysisBadge}
                              style={{
                                background: analysis.overall_score >= 70 ? '#16a34a' : analysis.overall_score >= 50 ? '#f59e0b' : '#dc2626',
                              }}
                            >
                              {analysis.overall_score}점
                            </span>
                          </div>

                          <p className={styles.teamAnalysisSummary}>
                            {analysis.summary}
                          </p>

                          <div className={styles.analysisSplitGrid}>
                            {/* 강점 */}
                            <div className={styles.strengthCard}>
                              <h4 className={styles.strengthTitle}>💪 강점</h4>
                              {analysis.strengths.length > 0 ? analysis.strengths.map((s, i) => (
                                <div key={i} className={styles.analysisItem}>
                                  <div className={styles.analysisItemHead}>
                                    <span className={styles.strengthItemTitle}>{s.title}</span>
                                    <span className={styles.strengthScore}>{s.score}</span>
                                  </div>
                                  <p className={styles.strengthDesc}>{s.description}</p>
                                </div>
                              )) : <p className={styles.analysisEmpty}>분석 중...</p>}
                            </div>

                            {/* 약점 */}
                            <div className={styles.weaknessCard}>
                              <h4 className={styles.weaknessTitle}>⚠️ 개선 필요</h4>
                              {analysis.weaknesses.length > 0 ? analysis.weaknesses.map((w, i) => (
                                <div key={i} className={styles.analysisItem}>
                                  <div className={styles.analysisItemHead}>
                                    <span className={styles.weaknessItemTitle}>{w.title}</span>
                                    <span className={styles.weaknessScore}>{w.score}</span>
                                  </div>
                                  <p className={styles.weaknessDesc}>{w.description}</p>
                                </div>
                              )) : <p className={styles.analysisEmpty}>약점 없음 👍</p>}
                            </div>
                          </div>

                          {/* 인사이트 */}
                          {analysis.insights.length > 0 && (
                            <div className={styles.insightsBox}>
                              {analysis.insights.map((insight, i) => (
                                <div key={i} className={styles.insightItem}>
                                  {insight}
                                </div>
                              ))}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>

                  {/* VAEP 선수 공헌도 랭킹 */}
                  <div className={styles.vaepSection}>
                    <div className={`card ${styles.vaepCard}`}>
                      {!vaepData ? (
                        <div className={styles.panelPlaceholder}>
                          VAEP 분석 불러오는 중...
                        </div>
                      ) : (
                        <>
                          <div className={`card-title ${styles.vaepTitle}`}>
                            선수 공헌도 (VAEP)
                            <span className={styles.vaepBadge}>
                              {vaepData.methodology}
                            </span>
                          </div>

                          <p className={styles.vaepSummary}>
                            총 팀 VAEP: <strong>{sf(vaepData.team_total_vaep)}</strong>점
                          </p>

                          <div className={styles.vaepGrid}>
                            {/* 전체 상위 5 */}
                            <div className={styles.vaepListCard}>
                              <h4 className={styles.vaepListTitlePrimary}>🏆 전체 TOP 5</h4>
                              {vaepData.top_players.slice(0, 5).map((p, i) => (
                                <div key={p.player_id} className={styles.vaepItemPrimary}>
                                  <span className={styles.vaepPlayerName}>
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
                                  <span className={styles.vaepScorePrimary}>
                                    {sf(p.total_vaep)}
                                  </span>
                                </div>
                              ))}
                            </div>

                            {/* 공격 상위 5 */}
                            <div className={styles.vaepListCard}>
                              <h4 className={styles.vaepListTitleOff}>⚽ 공격 TOP 5</h4>
                              {vaepData.top_offensive.slice(0, 5).map((p) => (
                                <div key={p.player_id} className={styles.vaepItemOff}>
                                  <span className={styles.vaepPlayerName}>{p.player_name}</span>
                                  <span className={styles.vaepScoreOff}>
                                    {sf(p.offensive_vaep)}
                                  </span>
                                </div>
                              ))}
                            </div>

                            {/* 수비 상위 5 */}
                            <div className={styles.vaepListCard}>
                              <h4 className={styles.vaepListTitleDef}>🛡️ 수비 TOP 5</h4>
                              {vaepData.top_defensive.slice(0, 5).map((p) => (
                                <div key={p.player_id} className={styles.vaepItemDef}>
                                  <span className={styles.vaepPlayerName}>{p.player_name}</span>
                                  <span className={styles.vaepScoreDef}>
                                    {sf(p.defensive_vaep)}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'patterns' && (
                <div>
                  {/* 피치 시각화 섹션 */}
                  <div className={`card ${styles.patternsCard}`}>
                    <div className={`card-title ${styles.patternsTitle}`}>
                      경기 상황 리플레이
                    </div>

                    {/* Phase 선택 - 버튼 스타일 */}
                    <div className={styles.phaseSection}>
                      <p className={styles.phaseLabel}>
                        공격 Phase 선택:
                      </p>
                      <div className={styles.phaseList}>
                        {phases.slice(0, 10).map((ph, idx) => (
                          <button
                            key={ph.phase_id}
                            onClick={() => loadPhaseReplay(ph.phase_id)}
                            className={`${styles.phaseButton} ${selectedPhase === ph.phase_id ? styles.phaseButtonActive : styles.phaseButtonInactive}`}
                          >
                            <div className={styles.phaseTitle}>
                              Phase {idx + 1} ⚽
                            </div>
                            <div className={styles.phaseMeta}>
                              패스 {ph.passes}회 · {Math.round(ph.duration)}초
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* 피치 리플레이 + 패턴 가로 배치 */}
                    <div className={styles.patternLayout}>
                      {/* 피치 리플레이 */}
                      <div className={`${styles.patternReplay} ${replayLoading ? styles.replayEase : ''}`}>
                        {replayLoading ? (
                          <div className={styles.patternLoading}>⏳ 로딩 중...</div>
                        ) : replayEvents.length > 0 ? (
                          <PitchReplay
                            events={replayEvents}
                            isPlaying={isPlaying}
                            onPlayPause={() => setIsPlaying(!isPlaying)}
                            playbackSpeed={playbackSpeed}
                            onSpeedChange={setPlaybackSpeed}
                          />
                        ) : (
                          <div className={styles.patternEmpty}>
                            <div className={styles.patternEmptyIcon}>🎬</div>
                            <p className={styles.patternEmptyText}>
                              위에서 Phase를 선택하세요
                            </p>
                          </div>
                        )}
                      </div>

                      {/* 패턴 통계 - 컴팩트 세로 배치 */}
                      <div className={styles.patternSide}>
                        <div className={styles.patternSideTitle}>
                          📊 패턴 TOP 5
                        </div>
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
              )}

              {activeTab === 'setpieces' && (
                setpieces.length > 0 ? (
                  <div className={styles.setpieceCard}>
                    {/* 상단 네비게이션 */}
                    <div className={styles.setpieceNav}>
                      <button
                        onClick={() => setSetpieceIndex(Math.max(0, setpieceIndex - 1))}
                        disabled={setpieceIndex === 0}
                        className={`${styles.setpieceNavButton} ${setpieceIndex === 0 ? styles.setpieceNavButtonDisabled : styles.setpieceNavButtonActive}`}
                      >
                        ←
                      </button>

                      {/* 현재 세트피스 정보 */}
                      <div className={styles.setpieceInfo}>
                        <span
                          className={`${styles.setpieceTag} ${setpieces[setpieceIndex]?.type.includes('Corner') ? styles.setpieceTagCorner : styles.setpieceTagFree}`}
                        >
                          {setpieces[setpieceIndex]?.type.includes('Corner') ? '코너킥' : '프리킥'}
                        </span>
                        <span className={styles.setpieceRate}>
                          슈팅 전환율 {sf((setpieces[setpieceIndex]?.shot_rate ?? 0) * 100, 0)}%
                        </span>
                        <span className={styles.setpieceIndex}>
                          {setpieceIndex + 1} / {setpieces.length}
                        </span>
                      </div>

                      <button
                        onClick={() => setSetpieceIndex(Math.min(setpieces.length - 1, setpieceIndex + 1))}
                        disabled={setpieceIndex === setpieces.length - 1}
                        className={`${styles.setpieceNavButton} ${setpieceIndex === setpieces.length - 1 ? styles.setpieceNavButtonDisabled : styles.setpieceNavButtonActive}`}
                      >
                        →
                      </button>
                    </div>

                    {/* 피치 시각화 */}
                    <div className={styles.setpiecePitch}>
                      <SetpiecePitch routine={setpieces[setpieceIndex]} />
                    </div>

                    {/* 하단 통계 */}
                    <div className={styles.setpieceStats}>
                      <div className={styles.setpieceStat}>
                        <div className={styles.setpieceStatValue}>{setpieces[setpieceIndex]?.frequency}</div>
                        <div className={styles.setpieceStatLabel}>발생 횟수</div>
                      </div>
                      <div className={styles.setpieceStat}>
                        <div className={styles.setpieceStatValue}>
                          {setpieces[setpieceIndex]?.swing_type === 'inswing' ? '인스윙' : '아웃스윙'}
                        </div>
                        <div className={styles.setpieceStatLabel}>킥 타입</div>
                      </div>
                      <div className={styles.setpieceStat}>
                        <div className={styles.setpieceStatValue}>
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
                        <div className={styles.setpieceStatLabel}>타겟존</div>
                      </div>
                    </div>

                    {/* 수비 제안 */}
                    <div className={styles.setpieceSuggest}>
                      💡 {setpieces[setpieceIndex]?.defense_suggestion}
                    </div>
                  </div>
                ) : (
                  <div className={`card ${styles.setpieceEmpty}`}>
                    {analysisLoading ? '세트피스 데이터를 불러오는 중...' : '세트피스 데이터가 없습니다.'}
                  </div>
                )
              )}

              {activeTab === 'network' && (
                <div className={styles.networkScroll}>
                  {/* 패스 네트워크 시각화 */}
                  <div className={styles.networkChart}>
                    {networkGraph ? (
                      <PassNetwork
                        nodes={networkGraph.nodes}
                        edges={networkGraph.edges}
                      />
                    ) : (
                      <div className={`card ${styles.networkPlaceholder}`}>
                        네트워크 로딩 중...
                      </div>
                    )}
                  </div>

                  {/* 허브 선수 카드 */}
                  <div className="pattern-grid">
                    {hubs.map((hub) => (
                      <div key={hub.player_id} className="card">
                        <div className="hub-card">
                          <div className="hub-avatar">{hub.position}</div>
                          <div className={`hub-info ${styles.hubInfo}`}>
                            <h4>{hub.player_name}</h4>
                            <p>{hub.main_position} • 허브 점수 {sf(hub.hub_score * 100, 0)}</p>
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
                </div>
              )}

              {activeTab === 'simulation' && (
                <div className={styles.preMatchSection}>
                  <div
                    className={`card ${styles.preMatchCard} ${simPulse ? styles.simPulse : ''}`}
                  >
                    <div className={styles.preMatchHeader}>
                      <div>
                        <div className={styles.preMatchTitle}>프리매치 예측</div>
                        <div className={styles.preMatchSubtitle}>최근 {ANALYSIS_GAMES}경기 기반 시뮬레이션</div>
                      </div>
                      <div className={styles.preMatchActions}>
                        {simUpdating && <span className={styles.updateBadge}>업데이트 중</span>}
                        <button
                          onClick={() => {
                            if (selectedTeam && opponent) {
                              simKeyRef.current = null;
                              runSimulation(selectedTeam, opponent);
                            }
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
                        const isSelf = selectedTeam?.team_id === team.team_id;
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
                              onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }}
                            />
                            <div className={styles.opponentInfo}>
                              <div className={styles.opponentName}>{team.team_name}</div>
                              <div className={styles.opponentRank}>{team.rank}위 · {team.points}점</div>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                    <div className={styles.opponentHint}>상대팀을 클릭하면 자동으로 예측이 갱신됩니다.</div>

                    <div className={`${styles.preMatchGrid} ${simStale ? styles.simDim : ''} ${simPulse ? styles.simPulse : ''}`}>
                      <div className={styles.matchupCard}>
                        <div className={styles.matchupLabel}>매치업</div>
                        <div className={styles.matchupRow}>
                          <div className={styles.matchupTeam}>
                            <Image
                              src={teamLogo(selectedTeam.team_name)}
                              alt={selectedTeam.team_name}
                              className="team-logo-lg"
                              width={48}
                              height={48}
                              onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }}
                            />
                            <div className={styles.matchupTeamInfo}>
                              <div className={styles.matchupTeamName}>{selectedTeam?.team_name}</div>
                              <div className={styles.matchupTeamMeta}>{selectedTeam?.rank}위 · {selectedTeam?.points}점</div>
                            </div>
                          </div>
                          <div className={styles.matchupVs}>VS</div>
                          <div className={styles.matchupTeamRight}>
                            {opponent ? (
                              <>
                                <div className={styles.matchupTeamInfo}>
                                  <div className={styles.matchupTeamName}>{opponent.team_name}</div>
                                  <div className={styles.matchupTeamMeta}>{opponent.rank}위 · {opponent.points}점</div>
                                </div>
                                <Image
                                  src={teamLogo(opponent.team_name)}
                                  alt={opponent.team_name}
                                  className="team-logo-lg"
                                  width={48}
                                  height={48}
                                  onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }}
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
                      <div className={styles.improvementPending}>
                        승률 개선 계산 중...
                      </div>
                    ) : simResult ? (
                      <div className={styles.improvement}>
                        승률 개선 {simResult.win_improvement >= 0 ? '+' : ''}{pct(simResult.win_improvement).toFixed(1)}%p
                        {simUpdating && <span className={styles.updateTag}>업데이트 중</span>}
                      </div>
                    ) : null}

                    <div className={`${styles.preMatchDetailGrid} ${simStale ? styles.simDim : ''} ${simPulse ? styles.simPulse : ''}`}>
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
                                  <div className={styles.tacticRank}>
                                    {s.priority}
                                  </div>
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
                                        <div className={styles.tacticScenarioDesc}>{relatedScenario.description}</div>
                                        <div className={styles.tacticScenarioMetrics}>
                                          <span>승</span> {fmtPct(relatedScenario.before.win)} → {fmtPct(relatedScenario.after.win)}
                                          <span className={styles.tacticScenarioDelta}>
                                            {relatedScenario.win_change >= 0 ? '+' : ''}
                                            {pct(relatedScenario.win_change).toFixed(1)}%p
                                          </span>
                                        </div>
                                        <div className={styles.tacticScenarioNote}>{relatedScenario.recommendation}</div>
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
                                    {sc.win_change >= 0 ? '+' : ''}{pct(sc.win_change).toFixed(1)}%p
                                  </div>
                                </div>
                                <div className={styles.scenarioDesc}>{sc.description}</div>
                                <div className={styles.scenarioMetrics}>
                                  <div><span>승</span> {fmtPct(sc.before.win)} → {fmtPct(sc.after.win)}</div>
                                  <div><span>무</span> {fmtPct(sc.before.draw)} → {fmtPct(sc.after.draw)}</div>
                                  <div><span>패</span> {fmtPct(sc.before.lose)} → {fmtPct(sc.after.lose)}</div>
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

                  <div className={styles.matchSection}>
                    <div className={styles.matchAnalysisHeader}>
                      <div className={styles.matchAnalysisTitle}>🔍 경기 분석 - 놓친 찬스</div>
                      <p className={styles.matchAnalysisDesc}>
                        분석할 경기를 선택하세요. 패배/무승부 경기에서 <strong className={styles.matchHighlight}>승리할 수 있었던 기회</strong>를 찾아냅니다.
                      </p>
                    </div>

                    {/* 1. 매치 리스트 뷰 (선택된 매치가 없을 때) */}
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
                                    className={styles.matchButton}
                                    style={{ borderLeft: `6px solid ${isDraw ? '#f59e0b' : '#ef4444'}` }}
                                  >
                                    <div>
                                      <div className={styles.matchDate}>{match.date}</div>
                                      <div className={styles.matchTeams}>
                                        {match.home_team} <span className={styles.matchVs}>vs</span> {match.away_team}
                                      </div>
                                      <div className={styles.matchHint}>
                                        {isDraw ? '무승부 경기 · 놓친 찬스 확인' : '패배 경기 · 승리 기회 재구성'}
                                      </div>
                                    </div>
                                    <div className={styles.matchRight}>
                                      <div className={styles.matchScore}>{match.score}</div>
                                      <div className={styles.matchResult} style={{ color: isDraw ? '#d97706' : '#dc2626' }}>
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

                    {/* 2. 상세 분석 뷰 (매치가 선택되었을 때) */}
                    {selectedMatch && (
                      <div className="fade-in">
                        <button
                          onClick={() => {
                            setSelectedMatch(null);
                            setChanceAnalysis(null);
                          }}
                          className={styles.analysisBack}
                        >
                          <span>←</span> 뒤로가기
                        </button>

                        {chanceLoading ? (
                          <div className={`${styles.analysisLoading} animate-fade-in`}>분석 중입니다...</div>
                        ) : chanceAnalysis ? (
                          <div className="analysis-result animate-fade-in">
                            <div className={`card ${styles.analysisCard}`}>
                              <h3 className={styles.analysisCardTitle}>
                                <span className={styles.analysisCardIcon}>💡</span>
                                AI 분석 리포트
                              </h3>
                              <div className={styles.analysisCardText}>
                                {chanceAnalysis.summary}
                              </div>
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
                </div>
              )}

              {activeTab === 'video' && (
                <div className={styles.videoSection}>
                  <VideoAnalysis />
                </div>
              )}

            </div>
          </>
        )}
      </main>
    </div>
  );
}
