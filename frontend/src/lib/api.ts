// API 클라이언트

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function fetchAPI<T>(endpoint: string): Promise<T> {
    const res = await fetch(`${API_BASE}${endpoint}`);
    if (!res.ok) {
        throw new Error(`API Error: ${res.status}`);
    }
    return res.json();
}

// Teams API
export async function getTeams() {
    return fetchAPI<{ teams: import('@/types').Team[]; count: number }>('/api/teams/');
}

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

// Patterns API
export async function getTeamPatterns(teamId: number, nGames: number = 5, nPatterns: number = 3) {
    return fetchAPI<{
        team_id: number;
        n_games_analyzed: number;
        total_events: number;
        patterns: import('@/types').Pattern[];
    }>(`/api/patterns/${teamId}?n_games=${nGames}&n_patterns=${nPatterns}`);
}

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

export async function getTeamAnalysis(teamId: number, nGames: number = 100) {
    return fetchAPI<TeamAnalysis>(`/api/patterns/${teamId}/analysis?n_games=${nGames}`);
}

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

export interface VAEPSummary {
    team_id: number;
    n_games_analyzed: number;
    team_total_vaep: number;
    top_players: VAEPPlayer[];
    top_offensive: VAEPPlayer[];
    top_defensive: VAEPPlayer[];
    methodology: string;
}

export async function getTeamVAEP(teamId: number, nGames: number = 100, nTop: number = 10) {
    return fetchAPI<VAEPSummary>(`/api/patterns/${teamId}/vaep?n_games=${nGames}&n_top=${nTop}`);
}

export async function getPhaseReplay(teamId: number, phaseId: number, nGames: number = 5) {
    return fetchAPI<{
        phase_id: number;
        events: import('@/types').ReplayEvent[];
    }>(`/api/patterns/${teamId}/phases/${phaseId}/replay?n_games=${nGames}`);
}

// Set-pieces API
export async function getTeamSetpieces(teamId: number, nGames: number = 5, nTop: number = 2) {
    return fetchAPI<{
        team_id: number;
        n_games_analyzed: number;
        setpiece_counts: { corners: number; freekicks: number };
        routines: import('@/types').SetPieceRoutine[];
    }>(`/api/setpieces/${teamId}?n_games=${nGames}&n_top=${nTop}`);
}

// Network API
export async function getTeamNetwork(teamId: number, nGames: number = 5, nHubs: number = 2) {
    return fetchAPI<{
        team_id: number;
        n_games_analyzed: number;
        hubs: import('@/types').Hub[];
        network_stats: { nodes: number; edges: number };
    }>(`/api/network/${teamId}?n_games=${nGames}&n_hubs=${nHubs}`);
}

export async function getNetworkGraph(teamId: number, nGames: number = 5) {
    return fetchAPI<{
        team_id: number;
        n_games_analyzed: number;
        graph: import('@/types').NetworkGraph;
    }>(`/api/network/${teamId}/graph?n_games=${nGames}`);
}

// Simulation API
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

// Pre-match Simulation
async function postAPI<T>(endpoint: string, data: object): Promise<T> {
    const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`API Error: ${res.status}`);
    return res.json();
}

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

// Match Analysis API
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

export async function matchList(teamId?: number) {
    const url = teamId ? `/api/simulation/matches?team_id=${teamId}` : '/api/simulation/matches';
    return fetchAPI<{ matches: MatchResult[] }>(url);
}

export async function matchChances(gameId: number) {
    return fetchAPI<ChanceAnalysis>(`/api/simulation/matches/${gameId}/chances`);
}
