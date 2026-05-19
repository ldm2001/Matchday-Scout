// K리그 전술 분석 대시보드
'use client';

import { useCallback, useRef, useState } from 'react';
import Image from 'next/image';
import { TeamStanding } from '@/types';
import { useStandings } from '@/hooks/useStandings';
import { useTeamSetpieces } from '@/hooks/useTeamSetpieces';
import { useTeamAnalysis } from '@/hooks/useTeamAnalysis';
import { useTeamPatterns } from '@/hooks/useTeamPatterns';
import { useTeamHubs } from '@/hooks/useTeamHubs';
import SetpiecesTab from '@/features/setpieces/SetpiecesTab';
import OverviewTab from '@/features/overview/OverviewTab';
import VideoTab from '@/features/video/VideoTab';
import PatternsTab from '@/features/patterns/PatternsTab';
import NetworkTab from '@/features/network/NetworkTab';
import SimulationTab from '@/features/simulation/SimulationTab';
import PostmatchTab from '@/features/postmatch/PostmatchTab';
import styles from './page.module.css';

// 탭 종류 정의
type Tab = 'overview' | 'patterns' | 'setpieces' | 'network' | 'simulation' | 'postmatch' | 'video';

// 메인 컴포넌트 - 팀 선택, 분석 탭, 시뮬레이션 기능 제공
export default function Home() {
  const { standings, loading } = useStandings();
  const [selectedTeam, setSelectedTeam] = useState<TeamStanding | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const contentScrollRef = useRef<HTMLDivElement | null>(null);

  const { patterns, loading: patternsLoading } = useTeamPatterns(selectedTeam?.team_id ?? null);
  const { setpieces, loading: setpiecesLoading } = useTeamSetpieces(selectedTeam?.team_id ?? null);
  const { hubs, loading: hubsLoading } = useTeamHubs(selectedTeam?.team_id ?? null);
  const { analysis } = useTeamAnalysis(selectedTeam?.team_id ?? null);

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
    { id: 'network', label: '선수 분석' },
    { id: 'simulation', label: '프리매치' },
    { id: 'postmatch', label: '포스트매치' },
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

  return (
    <div className="layout">
      {/* 사이드바 - 순위표 */}
      <aside className="sidebar">
        <div className="logo">
          <Image
            src="/logos/kleague-wordmark.png"
            alt="K LEAGUE"
            className="kleague-wordmark"
            width={180}
            height={32}
            priority
          />
          <div className="logo-sub">Matchday Scout</div>
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
              <div className="team-header" key={selectedTeam.team_id}>
                <Image
                  src={teamLogo(selectedTeam.team_name)}
                  alt={selectedTeam.team_name}
                  className="team-header-logo"
                  width={64}
                  height={64}
                  priority
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
                <OverviewTab
                  patterns={patterns}
                  hubs={hubs}
                  setpieces={setpieces}
                  patternsLoading={patternsLoading}
                  hubsLoading={hubsLoading}
                  setpiecesLoading={setpiecesLoading}
                  analysis={analysis}
                />
              )}

              {activeTab === 'patterns' && (
                <PatternsTab
                  teamId={selectedTeam?.team_id ?? null}
                  patterns={patterns}
                />
              )}

              {activeTab === 'setpieces' && (
                <SetpiecesTab
                  teamId={selectedTeam?.team_id ?? null}
                  setpieces={setpieces}
                  loading={setpiecesLoading}
                />
              )}

              {activeTab === 'network' && (
                <NetworkTab teamId={selectedTeam?.team_id ?? null} hubs={hubs} />
              )}

              {activeTab === 'simulation' && (
                <SimulationTab
                  ourTeam={selectedTeam}
                  standings={standings}
                  teamLogo={teamLogo}
                />
              )}

              {activeTab === 'postmatch' && <PostmatchTab ourTeam={selectedTeam} />}

              {activeTab === 'video' && <VideoTab />}

            </div>
          </>
        )}
      </main>
    </div>
  );
}
