# 패스 네트워크 분석 및 허브 탐지
import pandas as pd
import numpy as np
import networkx as nx
from typing import Dict, List
from functools import lru_cache
import math

from ..core.data import team_events
from ..core.spec import Analyzer


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


class NetworkAnalyzer(Analyzer):
    def __init__(self, events_df: pd.DataFrame, limit: int = 2):
        self.events = events_df
        self.graph = None
        self.player_stats = {}
        self.passes = None
        self.limit = limit
        
    def net_graph(self) -> nx.DiGraph:
        self.graph = nx.DiGraph()
        pass_cols = [
            "game_id",
            "action_id",
            "team_id",
            "player_id",
            "player_name_ko",
            "position_name",
            "main_position",
            "start_x",
            "start_y",
        ]
        recv_cols = ["game_id", "action_id", "team_id", "player_id"]
        passes = self.events[self.events["type_name"] == "Pass"][pass_cols].copy()
        received = self.events[self.events["type_name"] == "Pass Received"][recv_cols].copy()

        if passes.empty:
            return self.graph

        passes["action_id"] = pd.to_numeric(passes["action_id"], errors="coerce")
        received["action_id"] = pd.to_numeric(received["action_id"], errors="coerce")
        passes = passes.dropna(subset=["game_id", "team_id", "action_id", "player_id"])
        received = received.dropna(subset=["game_id", "team_id", "action_id", "player_id"])
        passes["game_id"] = passes["game_id"].astype(int)
        passes["team_id"] = passes["team_id"].astype(int)
        passes["action_id"] = passes["action_id"].astype(int)
        received["game_id"] = received["game_id"].astype(int)
        received["team_id"] = received["team_id"].astype(int)
        received["action_id"] = received["action_id"].astype(int)
        self.passes = passes
        if passes.empty:
            return self.graph

        node_rows = passes.drop_duplicates("player_id")
        for _, row in node_rows.iterrows():
            player_id = row.get("player_id")
            if pd.isna(player_id):
                continue
            self.graph.add_node(
                num_int(player_id),
                name=str(row.get("player_name_ko", str(player_id))),
                position=str(row.get("position_name", "Unknown")),
                main_position=str(row.get("main_position", "Unknown")),
            )

        if received.empty:
            return self.graph

        action_max = int(max(passes["action_id"].max(), received["action_id"].max()))
        team_max = int(max(passes["team_id"].max(), received["team_id"].max()))
        action_mult = action_max + 1
        team_mult = action_mult * (team_max + 1)
        passes["key"] = passes["game_id"] * team_mult + passes["team_id"] * action_mult + passes["action_id"]
        received["key"] = received["game_id"] * team_mult + received["team_id"] * action_mult + received["action_id"]
        passes = passes.sort_values("key")
        received = received.sort_values("key")

        pairs = pd.merge_asof(
            passes,
            received,
            on="key",
            direction="forward",
            suffixes=("", "_recv"),
        )
        pairs = pairs.dropna(subset=["player_id_recv"])
        pairs["action_gap"] = pairs["action_id_recv"] - pairs["action_id"]
        pairs = pairs[pairs["action_gap"] >= 0]
        pairs = pairs[pairs["action_gap"] <= 30]
        pairs = pairs[pairs["player_id"] != pairs["player_id_recv"]]
        if pairs.empty:
            return self.graph

        edge_counts = (
            pairs.groupby(["player_id", "player_id_recv"])
            .size()
            .reset_index(name="weight")
        )
        for _, row in edge_counts.iterrows():
            passer = num_int(row.get("player_id"))
            receiver = num_int(row.get("player_id_recv"))
            if passer in self.graph.nodes and receiver in self.graph.nodes:
                self.graph.add_edge(passer, receiver, weight=num_int(row.get("weight", 1)))
        
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
                'key_connections': self.link_list(player_id),
                'disruption_impact': self.impact_stat(player_id)
            })
        return hubs
    
    def link_list(self, player_id, n_connections: int = 3) -> List[Dict]:
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
        passes = self.passes
        if passes is None:
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

    def data(self) -> Dict:
        return {'hubs': self.hub_list(self.limit), 'network': self.net_data()}


def team_net(events_df: pd.DataFrame, n_hubs: int = 2) -> Dict:
    analyzer = NetworkAnalyzer(events_df, n_hubs)
    return analyzer.data()


@lru_cache(maxsize=128)
def net_box(team_id: int, n_games: int, n_hubs: int, mark: tuple) -> Dict:
    events = team_events(team_id, n_games)
    if len(events) == 0:
        return {}
    return team_net(events, n_hubs)
