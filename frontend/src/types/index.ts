// API 타입 정의 - 백엔드 응답과 일치하는 인터페이스 모음

// 팀 기본 정보
export interface Team {
    team_id: number;
    team_name: string;
}

// 공격 패턴 클러스터 정보
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

// 세트피스 루틴 정보 (코너킥/프리킥)
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

// 빌드업 허브 선수 정보
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

// 선수 간 패스 연결 정보
export interface Connection {
    type: 'passes_to' | 'receives_from';
    player_name: string;
    position: string;
    count: number;
}

// 허브 차단 시 영향도 분석
export interface DisruptionImpact {
    impact_score: number;
    edges_removed: number;
    component_change: number;
    description: string;
}

// 패스 네트워크 그래프 데이터
export interface NetworkGraph {
    nodes: NetworkNode[];
    edges: NetworkEdge[];
}

// 네트워크 노드 (선수)
export interface NetworkNode {
    id: string;
    name: string;
    position: string;
    hub_score: number;
    passes_total: number;
}

// 네트워크 엣지 (패스 연결)
export interface NetworkEdge {
    source: string;
    target: string;
    weight: number;
}

// 취약점 체인 분석 결과
export interface VulnerabilityChain {
    step1: ChainStep;
    step2: ChainStep;
    step3: ChainStep;
}

// 취약점 체인 단계
export interface ChainStep {
    action: string;
    expected_result: string;
}

// 압박 시뮬레이션 결과
export interface PressingSimulation {
    player_id: number;
    total_passes: number;
    scenario_a: Scenario;
    scenario_b: Scenario;
    on_failure_followups: Record<string, number>;
    recommendation: string;
}

// 시뮬레이션 시나리오
export interface Scenario {
    name: string;
    pass_success_rate: number;
    pass_failure_rate: number;
    description: string;
}

// 공격 페이즈 리플레이 이벤트
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
