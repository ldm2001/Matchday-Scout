# 패스 네트워크 분석 및 허브 탐지
import pandas as pd
import numpy as np
import networkx as nx
from typing import Dict, List
from collections import Counter
import math


def num(value, default=0.0):
    if value is None:
        return default
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return default
    try:
        result = float(value)
        return default if math.isnan(result) or math.isinf(result) else result
    except:
        return default


def num_int(value, default=0):
    try:
        return int(num(value, default))
    except:
        return default


class NetworkAnalyzer:
    def __init__(self, events_df: pd.DataFrame):
        self.events = events_df
        self.graph = None
        self.player_stats = {}
        
    def net_graph(self) -> nx.DiGraph:
        self.graph = nx.DiGraph()
        passes = self.events[self.events['type_name'] == 'Pass'].copy()
        pass_received = self.events[self.events['type_name'] == 'Pass Received'].copy()
        
        for player_id in passes['player_id'].unique():
            if pd.isna(player_id): continue
            player_passes = passes[passes['player_id'] == player_id]
            if len(player_passes) > 0:
                first_row = player_passes.iloc[0]
                self.graph.add_node(num_int(player_id),
                    name=str(first_row.get('player_name_ko', str(player_id))),
                    position=str(first_row.get('position_name', 'Unknown')),
                    main_position=str(first_row.get('main_position', 'Unknown')))
        
        pass_counts = Counter()
        for game_id in passes['game_id'].unique():
            game_passes = passes[passes['game_id'] == game_id].sort_values('action_id')
            game_received = pass_received[pass_received['game_id'] == game_id].sort_values('action_id')
            
            for _, pass_event in game_passes.iterrows():
                passer_id = pass_event['player_id']
                if pd.isna(passer_id): continue
                next_received = game_received[game_received['action_id'] > pass_event['action_id']]
                if len(next_received) > 0:
                    receiver_event = next_received.iloc[0]
                    if receiver_event['team_id'] == pass_event['team_id']:
                        receiver_id = receiver_event['player_id']
                        if not pd.isna(receiver_id) and passer_id != receiver_id:
                            pass_counts[(num_int(passer_id), num_int(receiver_id))] += 1
        
        for (passer, receiver), count in pass_counts.items():
            if passer in self.graph.nodes and receiver in self.graph.nodes:
                self.graph.add_edge(passer, receiver, weight=count)
        
        return self.graph
    
    def cent(self) -> Dict:
        if self.graph is None: self.net_graph()
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
            hub_score = 0.3 * num(degree_cent.get(node, 0)) + 0.4 * num(betweenness_cent.get(node, 0)) + 0.3 * num(pagerank.get(node, 0))
            result[node] = {
                'name': str(node_data.get('name', str(node))),
                'position': str(node_data.get('position', 'Unknown')),
                'main_position': str(node_data.get('main_position', 'Unknown')),
                'degree': num(degree_cent.get(node, 0)),
                'betweenness': num(betweenness_cent.get(node, 0)),
                'pagerank': num(pagerank.get(node, 0)),
                'passes_received': num_int(in_degree.get(node, 0)),
                'passes_made': num_int(out_degree.get(node, 0)),
                'hub_score': round(num(hub_score), 4)
            }
        return result
    
    def hub_list(self, n_hubs: int = 2) -> List[Dict]:
        cent = self.cent()
        if not cent: return []
        
        sorted_players = sorted(cent.items(), key=lambda x: x[1]['hub_score'], reverse=True)
        hubs = []
        for player_id, stats in sorted_players[:n_hubs]:
            hubs.append({
                'player_id': num_int(player_id), 'player_name': str(stats['name']),
                'position': str(stats['position']), 'main_position': str(stats['main_position']),
                'hub_score': num(stats['hub_score']), 'betweenness': num(stats['betweenness']),
                'pagerank': num(stats['pagerank']), 'passes_received': num_int(stats['passes_received']),
                'passes_made': num_int(stats['passes_made']),
                'key_connections': self.link_set(player_id),
                'disruption_impact': self.impact_stat(player_id)
            })
        return hubs
    
    def link_set(self, player_id, n_connections: int = 3) -> List[Dict]:
        if self.graph is None or player_id not in self.graph.nodes: return []
        
        connections = []
        try:
            out_sorted = sorted(self.graph.out_edges(player_id, data=True), key=lambda x: x[2].get('weight', 0), reverse=True)
            for _, target, data in out_sorted[:n_connections]:
                if target in self.graph.nodes:
                    connections.append({'type': 'passes_to', 'player_name': str(self.graph.nodes[target].get('name', '')),
                        'position': str(self.graph.nodes[target].get('position', '')), 'count': num_int(data.get('weight', 0))})
        except: pass
        
        try:
            in_sorted = sorted(self.graph.in_edges(player_id, data=True), key=lambda x: x[2].get('weight', 0), reverse=True)
            for source, _, data in in_sorted[:n_connections]:
                if source in self.graph.nodes:
                    connections.append({'type': 'receives_from', 'player_name': str(self.graph.nodes[source].get('name', '')),
                        'position': str(self.graph.nodes[source].get('position', '')), 'count': num_int(data.get('weight', 0))})
        except: pass
        
        return connections
    
    def impact_stat(self, player_id) -> Dict:
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
            
            return {'impact_score': num_int(impact_score), 'edges_removed': num_int(edges_removed),
                    'component_change': num_int(component_change), 'description': desc}
        except:
            return default
    
    def net_data(self) -> Dict:
        if self.graph is None: self.net_graph()
        
        cent = self.cent()
        passes = self.events[self.events['type_name'] == 'Pass'].copy()
        
        nodes = []
        for node_id in self.graph.nodes:
            node_data = self.graph.nodes[node_id]
            c = cent.get(node_id, {})
            player_passes = passes[passes['player_id'] == node_id]
            nodes.append({
                'id': str(node_id), 'name': str(node_data.get('name', str(node_id))),
                'position': str(node_data.get('position', '')), 'hub_score': num(c.get('hub_score', 0)),
                'passes_total': num_int(c.get('passes_received', 0)) + num_int(c.get('passes_made', 0)),
                'avg_x': round(num(player_passes['start_x'].mean(), 50), 1),
                'avg_y': round(num(player_passes['start_y'].mean(), 34), 1)
            })
        
        edges = [{'source': str(s), 'target': str(t), 'weight': num_int(d.get('weight', 1))} 
                 for s, t, d in self.graph.edges(data=True)]
        
        return {'nodes': nodes, 'edges': edges}


def team_net(events_df: pd.DataFrame, n_hubs: int = 2) -> Dict:
    analyzer = NetworkAnalyzer(events_df)
    return {'hubs': analyzer.hub_list(n_hubs), 'network': analyzer.net_data()}
