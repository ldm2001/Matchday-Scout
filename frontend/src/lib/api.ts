// API 클라이언트 - 백엔드 API 호출 함수 모음

// 브라우저 환경에서는 상대 경로, SSR에서는 환경 변수 사용
const getApiBase = (): string => {
    // 브라우저 환경: 상대 경로 사용 (Nginx 프록시)
    if (typeof window !== 'undefined') {
        return '';
    }
    // 서버 사이드 렌더링: 환경 변수 또는 localhost 사용
    return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
};

// 재시도 대상 HTTP 상태 코드
const RETRY_STATUSES = new Set([500, 502, 503, 504]);
const RETRY_LIMIT = 2;
const RETRY_DELAY_MS = 400;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// 서버 오류 시 자동 재시도 fetch
async function fetchWithRetry(url: string, init?: RequestInit, retries: number = RETRY_LIMIT) {
    let attempt = 0;
    while (true) {
        const res = await fetch(url, init);
        if (res.ok || !RETRY_STATUSES.has(res.status) || attempt >= retries) {
            return res;
        }
        attempt += 1;
        await sleep(RETRY_DELAY_MS * attempt);
    }
}

// GET 요청 래퍼
async function fetchAPI<T>(endpoint: string): Promise<T> {
    const API_BASE = getApiBase();

    // 프로덕션 환경에서 잘못된 경로 감지
    if (typeof window !== 'undefined' && process.env.NODE_ENV === 'production') {
        const fullUrl = `${API_BASE}${endpoint}`;
        if (fullUrl.includes('localhost') || fullUrl.startsWith('http://') || fullUrl.startsWith('https://')) {
            console.warn('[API] 잘못된 API 경로 감지:', fullUrl, '→ 상대 경로로 변경해야 함');
        }
    }

    const res = await fetchWithRetry(`${API_BASE}${endpoint}`);
    if (!res.ok) {
        throw new Error(`API Error: ${res.status}`);
    }
    return res.json();
}

// POST 요청 래퍼
async function postAPI<T>(endpoint: string, payload: unknown): Promise<T> {
    const API_BASE = getApiBase();
    const res = await fetchWithRetry(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (!res.ok) {
        throw new Error(`API Error: ${res.status}`);
    }
    return res.json();
}

// 팀 목록 조회
export async function getTeams() {
    return fetchAPI<{ teams: import('@/types').Team[]; count: number }>('/api/teams/');
}

// 팀 순위표 조회
export async function getTeamsOverview() {
    return fetchAPI<{
        standings: Array<{
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
        }>;
        total_teams: number;
    }>('/api/teams/overview');
}

// 팀 상세 정보 조회
export async function getTeamInfo(teamId: number) {
    return fetchAPI<{
        team_id: number;
        team_name: string;
        total_matches: number;
        recent_matches: Array<{
            game_id: number;
            date: string;
            opponent: string;
            venue: string;
            score: string;
        }>;
    }>(`/api/teams/${teamId}`);
}

// 팀 공격 패턴 조회
export async function getTeamPatterns(teamId: number, nGames: number = 5, nPatterns: number = 3) {
    return fetchAPI<{
        team_id: number;
        n_games_analyzed: number;
        total_events: number;
        patterns: import('@/types').Pattern[];
    }>(`/api/patterns/${teamId}?n_games=${nGames}&n_patterns=${nPatterns}`);
}

// 팀 공격 페이즈 목록 조회
export async function getTeamPhases(teamId: number, nGames: number = 5) {
    return fetchAPI<{
        team_id: number;
        n_games_analyzed: number;
        total_phases: number;
        phases: Array<{
            phase_id: number;
            length: number;
            duration: number;
            has_shot: boolean;
            passes: number;
            start_zone: string;
            event_sequence: string;
        }>;
    }>(`/api/patterns/${teamId}/phases?n_games=${nGames}`);
}

// 팀 분석 결과 타입
export interface TeamAnalysis {
    team_id: number;
    overall_score: number;
    strengths: Array<{
        category: string;
        title: string;
        description: string;
        score: number;
    }>;
    weaknesses: Array<{
        category: string;
        title: string;
        description: string;
        score: number;
    }>;
    insights: string[];
    summary: string;
}

// AI 기반 팀 강약점 분석 조회
export async function getTeamAnalysis(teamId: number, nGames: number = 100) {
    return fetchAPI<TeamAnalysis>(`/api/patterns/${teamId}/analysis?n_games=${nGames}`);
}

// VAEP 선수 가치 타입
export interface VAEPPlayer {
    player_id: number;
    player_name: string;
    position: string;
    total_vaep: number;
    avg_vaep: number;
    actions: number;
    offensive_vaep: number;
    defensive_vaep: number;
    passing_vaep: number;
}

// VAEP 팀 요약 타입
export interface VAEPSummary {
    team_id: number;
    n_games_analyzed: number;
    team_total_vaep: number;
    top_players: VAEPPlayer[];
    top_offensive: VAEPPlayer[];
    top_defensive: VAEPPlayer[];
    methodology: string;
}

// 팀 VAEP 분석 조회
export async function getTeamVAEP(teamId: number, nGames: number = 100, nTop: number = 10) {
    return fetchAPI<VAEPSummary>(`/api/patterns/${teamId}/vaep?n_games=${nGames}&n_top=${nTop}`);
}

// 공격 페이즈 리플레이 데이터 조회
export async function getPhaseReplay(teamId: number, phaseId: number, nGames: number = 5) {
    return fetchAPI<{
        phase_id: number;
        events: import('@/types').ReplayEvent[];
    }>(`/api/patterns/${teamId}/phases/${phaseId}/replay?n_games=${nGames}`);
}

// 팀 세트피스 루틴 조회
export async function getTeamSetpieces(teamId: number, nGames: number = 5, nTop: number = 2) {
    return fetchAPI<{
        team_id: number;
        n_games_analyzed: number;
        setpiece_counts: { corners: number; freekicks: number };
        routines: import('@/types').SetPieceRoutine[];
    }>(`/api/setpieces/${teamId}?n_games=${nGames}&n_top=${nTop}`);
}

// 팀 빌드업 허브 조회
export async function getTeamNetwork(teamId: number, nGames: number = 5, nHubs: number = 2) {
    return fetchAPI<{
        team_id: number;
        n_games_analyzed: number;
        hubs: import('@/types').Hub[];
        network_stats: { nodes: number; edges: number };
    }>(`/api/network/${teamId}?n_games=${nGames}&n_hubs=${nHubs}`);
}

// 패스 네트워크 그래프 조회
export async function getNetworkGraph(teamId: number, nGames: number = 5) {
    return fetchAPI<{
        team_id: number;
        n_games_analyzed: number;
        graph: import('@/types').NetworkGraph;
    }>(`/api/network/${teamId}/graph?n_games=${nGames}`);
}

// 압박 시뮬레이션 실행
export async function simulatePressing(teamId: number, playerId: number, nGames: number = 5) {
    return fetchAPI<{
        team_id: number;
        target_player_id: number;
        n_games_analyzed: number;
        pressing_simulation: import('@/types').PressingSimulation;
        vulnerability_chain: {
            player_id: number;
            vulnerability_chain: import('@/types').VulnerabilityChain;
            summary: string;
        };
    }>(`/api/simulation/${teamId}/pressing/${playerId}?n_games=${nGames}`);
}

// 비디오 클립 정보 타입
export interface VideoClip {
    url: string;
    video_id: string;
    start: number;
    fps?: number | null;
    width?: number | null;
    height?: number | null;
}

// 비디오 키 모멘트 타입
export interface VideoMoment {
    ts: number;
    label: string;
    actual: { x: number; y: number };
    suggest: { x: number; y: number };
    delta: number;
    note: string;
    conf: number;
    overlay?: {
        actual_px: { x: number; y: number };
        suggest_px: { x: number; y: number };
        goal_px: { x: number; y: number };
        angle: number;
        quality: number;
    };
}

// 비디오 분석 리포트 타입
export interface VideoReport {
    job_id: string;
    status: string;
    clip: VideoClip;
    moments: VideoMoment[];
    notes: string[];
    mode: string;
    heatmap?: {
        rows: number;
        cols: number;
        max: number;
        cells: Array<{
            row: number;
            col: number;
            value: number;
            poly_px: Array<{ x: number; y: number }>;
        }>;
        suggest_cells: Array<{
            row: number;
            col: number;
            value: number;
            poly_px: Array<{ x: number; y: number }>;
        }>;
    };
}

// 비디오 분석 작업 타입
export interface VideoJob {
    job_id: string;
    status: string;
    created?: number;
    updated?: number;
    report?: VideoReport | null;
    error?: string | null;
}

// URL로 비디오 분석 작업 시작
export async function startVideoJob(url: string) {
    return postAPI<VideoJob>('/api/video/jobs', { url });
}

// 파일 업로드로 비디오 분석 작업 시작
export async function uploadVideoJob(file: File, url: string = '') {
    const API_BASE = getApiBase();
    const form = new FormData();
    form.append('file', file);
    form.append('url', url);
    const res = await fetchWithRetry(`${API_BASE}/api/video/upload`, {
        method: 'POST',
        body: form,
    });
    if (!res.ok) {
        let detail = '';
        try {
            const payload = await res.json();
            detail = payload?.detail || '';
        } catch {
            detail = '';
        }
        throw new Error(detail || `API Error: ${res.status}`);
    }
    return res.json();
}

// 비디오 분석 작업 상태 조회
export async function getVideoJob(jobId: string) {
    return fetchAPI<VideoJob>(`/api/video/jobs/${jobId}`);
}

// 전체 전술 분석 조회
export async function getFullTacticalAnalysis(teamId: number, nGames: number = 5) {
    return fetchAPI<{
        team_id: number;
        n_games_analyzed: number;
        pressing_targets: Array<{
            hub: import('@/types').Hub;
            pressing_simulation: import('@/types').PressingSimulation;
            vulnerability_chain: import('@/types').VulnerabilityChain;
            summary: string;
        }>;
    }>(`/api/simulation/${teamId}/full-analysis?n_games=${nGames}`);
}

// 경기 전 시뮬레이션 실행
export async function runPreMatchSimulation(ourTeamId: number, opponentId: number, nGames: number = 5) {
    return postAPI<{
        our_team_id: number;
        opponent_id: number;
        base_prediction: { win: number; draw: number; lose: number };
        optimal_prediction: { win: number; draw: number; lose: number };
        win_improvement: number;
        tactical_suggestions: Array<{
            priority: number;
            tactic: string;
            reason: string;
            expected_effect: string;
            win_prob_change: string;
        }>;
        scenarios: Array<{
            scenario: string;
            description: string;
            before: { win: number; draw: number; lose: number };
            after: { win: number; draw: number; lose: number };
            win_change: number;
            recommendation: string;
        }>;
    }>('/api/simulation/pre-match', {
        our_team_id: ourTeamId,
        opponent_id: opponentId,
        n_games: nGames,
    });
}

// 경기 결과 타입
export interface MatchResult {
    game_id: number;
    date: string;
    home_team: string;
    away_team: string;
    home_team_id: number;
    away_team_id: number;
    score: string;
    result: 'home_win' | 'away_win' | 'draw';
    result_text: string;
    venue: string;
}

// 키 모멘트 (놓친 찬스) 타입
export interface KeyMoment {
    time: number;
    time_display?: string;
    period: number;
    player: string;
    player_position?: string;
    action: string;
    result: string;
    position: { x: number; y: number };

    // 상세 분석
    original_situation?: {
        description: string;
        position: { x: number; y: number };
        distance_to_goal: number;
        zone: string;
    };

    failure_analysis?: {
        reasons: string[];
        xg: number;
    };

    suggestion: {
        type: string;
        target_x?: number;
        target_y?: number;
        target_position?: { x: number; y: number };
        description: string;
        reasons?: string[];
        expected_xg?: number;
        xg_improvement?: string;
    };

    play_sequence?: Array<{
        time: number;
        player: string;
        position: string;
        action: string;
        result: string;
        start_x: number;
        start_y: number;
        end_x: number;
        end_y: number;
    }>;

    setup_play: {
        player: string;
        action: string;
        description?: string;
        from_x: number;
        from_y: number;
        to_x: number;
        to_y: number;
    } | null;
}

// 찬스 분석 결과 타입
export interface ChanceAnalysis {
    game_id: number;
    date: string;
    home_team: { id: number; name: string; score: number };
    away_team: { id: number; name: string; score: number };
    result: string;
    score: string;
    summary: string;
    chances: Array<{
        team_id: number;
        team_name: string;
        key_moments: KeyMoment[];
    }>;
}

// 팀 경기 목록 조회
export async function matchList(teamId?: number) {
    const url = teamId ? `/api/simulation/matches?team_id=${teamId}` : '/api/simulation/matches';
    return fetchAPI<{ matches: MatchResult[] }>(url);
}

// 경기별 놓친 찬스 분석 조회
export async function matchChances(gameId: number) {
    return fetchAPI<ChanceAnalysis>(`/api/simulation/matches/${gameId}/chances`);
}
