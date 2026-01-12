# 패스 네트워크 분석 및 허브 탐지
import pandas as pd
import numpy as np
import networkx as nx
from typing import Dict, List
from collections import Counter
import math


def safe_float(value, default=0.0):
    if value is None:
        return default
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return default
    try:
        result = float(value)
        return default if math.isnan(result) or math.isinf(result) else result
    except:
        return default


def safe_int(value, default=0):
    try:
        return int(safe_float(value, default))
    except:
        return default


class NetworkAnalyzer:
    def __init__(self, events_df: pd.DataFrame):
        self.events = events_df
        self.graph = None
        self.player_stats = {}
        self._centrality_cache = None

    def pass_network(self) -> nx.DiGraph:
        self._centrality_cache = None
        self.graph = nx.DiGraph()
        passes = self.events[self.events['type_name'] == 'Pass'].copy()
        pass_received = self.events[self.events['type_name'] == 'Pass Received'].copy()
        
        for player_id in passes['player_id'].unique():
            if pd.isna(player_id): continue
            player_passes = passes[passes['player_id'] == player_id]
            if len(player_passes) > 0:
                first_row = player_passes.iloc[0]
                self.graph.add_node(safe_int(player_id),
                    name=str(first_row.get('player_name_ko', str(player_id))),
                    position=str(first_row.get('position_name', 'Unknown')),
                    main_position=str(first_row.get('main_position', 'Unknown')))
        
        if passes.empty or pass_received.empty:
            return self.graph

        pass_cols = ['game_id', 'team_id', 'action_id', 'player_id']
        recv_cols = ['game_id', 'team_id', 'action_id', 'player_id']

        passes_sorted = passes[pass_cols].sort_values(['game_id', 'team_id', 'action_id'])
        received_sorted = pass_received[recv_cols].sort_values(['game_id', 'team_id', 'action_id'])

        merged = pd.merge_asof(
            passes_sorted,
            received_sorted,
            on='action_id',
            by=['game_id', 'team_id'],
            direction='forward',
            allow_exact_matches=False,
            suffixes=('_pass', '_recv'),
        )
        merged = merged.dropna(subset=['player_id_pass', 'player_id_recv'])
        merged = merged[merged['player_id_pass'] != merged['player_id_recv']]

        pass_counts = merged.groupby(['player_id_pass', 'player_id_recv']).size()
        for (passer, receiver), count in pass_counts.items():
            passer_id = safe_int(passer)
            receiver_id = safe_int(receiver)
            if passer_id in self.graph.nodes and receiver_id in self.graph.nodes:
                self.graph.add_edge(passer_id, receiver_id, weight=int(count))
        
        return self.graph
    
    def centrality(self) -> Dict:
        if self._centrality_cache is not None:
            return self._centrality_cache
        if self.graph is None: self.pass_network()
        if len(self.graph.nodes) == 0: return {}
        
        try: degree_cent = nx.degree_centrality(self.graph)
        except: degree_cent = {n: 0 for n in self.graph.nodes}
        try: betweenness_cent = nx.betweenness_centrality(self.graph, weight='weight')
        except: betweenness_cent = {n: 0 for n in self.graph.nodes}
        try: pagerank = nx.pagerank(self.graph, weight='weight')
        except: pagerank = {n: 1.0/max(len(self.graph.nodes), 1) for n in self.graph.nodes}
        
        in_degree = dict(self.graph.in_degree(weight='weight'))
        out_degree = dict(self.graph.out_degree(weight='weight'))
        
        result = {}
        for node in self.graph.nodes:
            node_data = self.graph.nodes[node]
            hub_score = 0.3 * safe_float(degree_cent.get(node, 0)) + 0.4 * safe_float(betweenness_cent.get(node, 0)) + 0.3 * safe_float(pagerank.get(node, 0))
            result[node] = {
                'name': str(node_data.get('name', str(node))),
                'position': str(node_data.get('position', 'Unknown')),
                'main_position': str(node_data.get('main_position', 'Unknown')),
                'degree': safe_float(degree_cent.get(node, 0)),
                'betweenness': safe_float(betweenness_cent.get(node, 0)),
                'pagerank': safe_float(pagerank.get(node, 0)),
                'passes_received': safe_int(in_degree.get(node, 0)),
                'passes_made': safe_int(out_degree.get(node, 0)),
                'hub_score': round(safe_float(hub_score), 4)
            }
        self._centrality_cache = result
        self._centrality_cache = result
        return result
    
    def find_hubs(self, n_hubs: int = 2) -> List[Dict]:
        cent = self.centrality()
        if not cent: return []
        
        sorted_players = sorted(cent.items(), key=lambda x: x[1]['hub_score'], reverse=True)
        hubs = []
        for player_id, stats in sorted_players[:n_hubs]:
            hubs.append({
                'player_id': safe_int(player_id), 'player_name': str(stats['name']),
                'position': str(stats['position']), 'main_position': str(stats['main_position']),
                'hub_score': safe_float(stats['hub_score']), 'betweenness': safe_float(stats['betweenness']),
                'pagerank': safe_float(stats['pagerank']), 'passes_received': safe_int(stats['passes_received']),
                'passes_made': safe_int(stats['passes_made']),
                'key_connections': self._key_connections(player_id),
                'disruption_impact': self._disruption_impact(player_id)
            })
        return hubs
    
    def _key_connections(self, player_id, n_connections: int = 3) -> List[Dict]:
        if self.graph is None or player_id not in self.graph.nodes: return []
        
        connections = []
        try:
            out_sorted = sorted(self.graph.out_edges(player_id, data=True), key=lambda x: x[2].get('weight', 0), reverse=True)
            for _, target, data in out_sorted[:n_connections]:
                if target in self.graph.nodes:
                    connections.append({'type': 'passes_to', 'player_name': str(self.graph.nodes[target].get('name', '')),
                        'position': str(self.graph.nodes[target].get('position', '')), 'count': safe_int(data.get('weight', 0))})
        except: pass
        
        try:
            in_sorted = sorted(self.graph.in_edges(player_id, data=True), key=lambda x: x[2].get('weight', 0), reverse=True)
            for source, _, data in in_sorted[:n_connections]:
                if source in self.graph.nodes:
                    connections.append({'type': 'receives_from', 'player_name': str(self.graph.nodes[source].get('name', '')),
                        'position': str(self.graph.nodes[source].get('position', '')), 'count': safe_int(data.get('weight', 0))})
        except: pass
        
        return connections
    
    def _disruption_impact(self, player_id) -> Dict:
        default = {'impact_score': 0, 'edges_removed': 0, 'component_change': 0, 'description': '압박 타겟'}
        if self.graph is None or player_id not in self.graph.nodes: return default
        
        try:
            original_edges = self.graph.number_of_edges()
            if original_edges == 0: return default
            
            test_graph = self.graph.copy()
            test_graph.remove_node(player_id)
            edges_removed = original_edges - test_graph.number_of_edges()
            
            try:
                component_change = nx.number_weakly_connected_components(test_graph) - nx.number_weakly_connected_components(self.graph)
            except:
                component_change = 0
            
            impact_score = min(100, int((edges_removed / max(original_edges, 1) * 50) + (component_change * 25)))
            player_name = str(self.graph.nodes[player_id].get('name', ''))
            
            if impact_score >= 70: desc = f"{player_name} 최우선 압박 타겟"
            elif impact_score >= 40: desc = f"{player_name} 압박 권장"
            else: desc = f"{player_name} 보조 타겟"
            
            return {'impact_score': safe_int(impact_score), 'edges_removed': safe_int(edges_removed),
                    'component_change': safe_int(component_change), 'description': desc}
        except:
            return default
    
    def network_data(self) -> Dict:
        if self.graph is None: self.pass_network()
        
        cent = self.centrality()
        passes = self.events[self.events['type_name'] == 'Pass'].copy()
        
        nodes = []
        for node_id in self.graph.nodes:
            node_data = self.graph.nodes[node_id]
            c = cent.get(node_id, {})
            player_passes = passes[passes['player_id'] == node_id]
            nodes.append({
                'id': str(node_id), 'name': str(node_data.get('name', str(node_id))),
                'position': str(node_data.get('position', '')), 'hub_score': safe_float(c.get('hub_score', 0)),
                'passes_total': safe_int(c.get('passes_received', 0)) + safe_int(c.get('passes_made', 0)),
                'avg_x': round(safe_float(player_passes['start_x'].mean(), 50), 1),
                'avg_y': round(safe_float(player_passes['start_y'].mean(), 34), 1)
            })
        
        edges = [{'source': str(s), 'target': str(t), 'weight': safe_int(d.get('weight', 1))} 
                 for s, t, d in self.graph.edges(data=True)]
        
        return {'nodes': nodes, 'edges': edges}


def team_network(events_df: pd.DataFrame, n_hubs: int = 2) -> Dict:
    analyzer = NetworkAnalyzer(events_df)
    return {'hubs': analyzer.find_hubs(n_hubs), 'network': analyzer.network_data()}
