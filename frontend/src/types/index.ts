// API 타입 정의

export interface Team {
    team_id: number;
    team_name: string;
}

export interface Pattern {
    cluster_id: number;
    frequency: number;
    shot_conversion_rate: number;
    avg_duration: number;
    avg_passes: number;
    avg_forward_progress: number;
    avg_start_zone: string;
    avg_end_zone: string;
    common_sequences: string[];
}

export interface SetPieceRoutine {
    type: string;
    cluster_id: number;
    frequency: number;
    shot_rate: number;
    primary_zone: string;
    swing_type: string;
    avg_target_x: number;
    avg_target_y: number;
    defense_suggestion: string;
}

export interface Hub {
    player_id: number;
    player_name: string;
    position: string;
    main_position: string;
    hub_score: number;
    betweenness: number;
    pagerank: number;
    passes_received: number;
    passes_made: number;
    key_connections: Connection[];
    disruption_impact: DisruptionImpact;
}

export interface Connection {
    type: 'passes_to' | 'receives_from';
    player_name: string;
    position: string;
    count: number;
}

export interface DisruptionImpact {
    impact_score: number;
    edges_removed: number;
    component_change: number;
    description: string;
}

export interface NetworkGraph {
    nodes: NetworkNode[];
    edges: NetworkEdge[];
}

export interface NetworkNode {
    id: string;
    name: string;
    position: string;
    hub_score: number;
    passes_total: number;
}

export interface NetworkEdge {
    source: string;
    target: string;
    weight: number;
}

export interface VulnerabilityChain {
    step1: ChainStep;
    step2: ChainStep;
    step3: ChainStep;
}

export interface ChainStep {
    action: string;
    expected_result: string;
}

export interface PressingSimulation {
    player_id: number;
    total_passes: number;
    scenario_a: Scenario;
    scenario_b: Scenario;
    on_failure_followups: Record<string, number>;
    recommendation: string;
}

export interface Scenario {
    name: string;
    pass_success_rate: number;
    pass_failure_rate: number;
    description: string;
}

export interface ReplayEvent {
    time: number;
    type: string;
    player: string;
    player_id: string;
    position: string;
    start_x: number;
    start_y: number;
    end_x: number;
    end_y: number;
    result: string;
}
