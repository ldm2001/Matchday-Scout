# 세트피스 루틴 분석기
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from typing import List, Dict
from collections import Counter


class SetPieceAnalyzer:
    SETPIECE_TYPES = ['Pass_Corner', 'Pass_Freekick', 'Shot_Freekick']
    ROUTINE_LENGTH = 5
    
    def __init__(self, events_df: pd.DataFrame):
        self.events = events_df.sort_values(['game_id', 'period_id', 'time_seconds'])
        
    def extract_routines(self) -> List[Dict]:
        routines = []
        
        for game_id in self.events['game_id'].unique():
            game_events = self.events[self.events['game_id'] == game_id].reset_index(drop=True)
            
            for i, row in game_events.iterrows():
                if row['type_name'] in self.SETPIECE_TYPES:
                    routine_events = game_events.iloc[i:i+self.ROUTINE_LENGTH+1]
                    if len(routine_events) >= 2:
                        routine = self._analyze_routine(row, routine_events)
                        if routine:
                            routines.append(routine)
        
        return routines
    
    def _analyze_routine(self, setpiece_event: pd.Series, routine_events: pd.DataFrame) -> Dict:
        routine = {
            'type': setpiece_event['type_name'],
            'game_id': setpiece_event['game_id'],
            'minute': setpiece_event['time_seconds'] / 60,
            'start_x': setpiece_event.get('start_x', 0),
            'start_y': setpiece_event.get('start_y', 0),
            'events': []
        }
        
        for _, event in routine_events.iterrows():
            routine['events'].append({
                'type': event['type_name'],
                'x': event.get('start_x', 0),
                'y': event.get('start_y', 0),
                'result': event.get('result_name', ''),
                'player': event.get('player_name_ko', '')
            })
        
        routine['has_shot'] = any(e['type'] in ['Shot', 'Shot_Freekick'] for e in routine['events'])
        routine['has_goal'] = any(e['type'] == 'Goal' for e in routine['events'])
        
        for e in routine['events'][1:]:
            if e['type'] in ['Pass Received', 'Pass']:
                routine['first_target_x'] = e['x']
                routine['first_target_y'] = e['y']
                routine['first_target_zone'] = self._zone(e['x'], e['y'])
                break
        else:
            routine['first_target_x'] = 0
            routine['first_target_y'] = 0
            routine['first_target_zone'] = 'unknown'
        
        if len(routine['events']) >= 2:
            start_y, target_y = routine['start_y'], routine['first_target_y']
            if start_y < 34:
                routine['swing_type'] = 'inswing' if target_y < 34 else 'outswing'
            else:
                routine['swing_type'] = 'inswing' if target_y > 34 else 'outswing'
        else:
            routine['swing_type'] = 'unknown'
        
        routine['sequence'] = '_'.join([e['type'] for e in routine['events']])
        return routine
    
    def _zone(self, x: float, y: float) -> str:
        dist = 105 - x
        if dist <= 6:
            return 'near_post' if y < 30 else ('far_post' if y > 38 else 'center')
        elif dist <= 16.5:
            return 'near_post' if y < 25 else ('far_post' if y > 43 else 'center')
        elif dist <= 25:
            return 'edge_box'
        return 'penalty_spot'
    
    def cluster_routines(self, routines: List[Dict], n_clusters: int = 3) -> Dict:
        if len(routines) < n_clusters:
            return {}
        
        features = [[r.get('first_target_x', 0), r.get('first_target_y', 0), 
                     1 if r.get('swing_type') == 'inswing' else 0,
                     len(r.get('events', [])), 1 if r.get('has_shot') else 0] for r in routines]
        
        X_scaled = StandardScaler().fit_transform(np.array(features))
        labels = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit_predict(X_scaled)
        
        clusters = {}
        for i, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = {'routines': [], 'count': 0, 'shot_count': 0, 'goal_count': 0}
            clusters[label]['routines'].append(routines[i])
            clusters[label]['count'] += 1
            if routines[i].get('has_shot'): clusters[label]['shot_count'] += 1
            if routines[i].get('has_goal'): clusters[label]['goal_count'] += 1
        
        for label in clusters:
            cluster_routines = clusters[label]['routines']
            zones = [r.get('first_target_zone', 'unknown') for r in cluster_routines]
            swings = [r.get('swing_type', 'unknown') for r in cluster_routines]
            clusters[label]['primary_zone'] = Counter(zones).most_common(1)[0][0]
            clusters[label]['swing_type'] = Counter(swings).most_common(1)[0][0]
            clusters[label]['shot_rate'] = clusters[label]['shot_count'] / clusters[label]['count']
            clusters[label]['avg_target_x'] = np.mean([r.get('first_target_x', 0) for r in cluster_routines])
            clusters[label]['avg_target_y'] = np.mean([r.get('first_target_y', 0) for r in cluster_routines])
        
        return clusters
    
    def top_routines(self, n_top: int = 2) -> List[Dict]:
        routines = self.extract_routines()
        if not routines:
            return []
        
        corners = [r for r in routines if 'Corner' in r['type']]
        freekicks = [r for r in routines if 'Freekick' in r['type']]
        results = []
        
        if len(corners) >= 3:
            corner_clusters = self.cluster_routines(corners, min(3, len(corners)))
            for label, info in sorted(corner_clusters.items(), key=lambda x: x[1]['shot_rate'], reverse=True)[:n_top]:
                results.append({
                    'type': 'Corner', 'cluster_id': int(label), 'frequency': info['count'],
                    'shot_rate': round(info['shot_rate'], 3), 'primary_zone': info['primary_zone'],
                    'swing_type': info['swing_type'], 'avg_target_x': round(info['avg_target_x'], 1),
                    'avg_target_y': round(info['avg_target_y'], 1),
                    'defense_suggestion': self._defense_suggestion(info)
                })
        
        if len(freekicks) >= 3:
            fk_clusters = self.cluster_routines(freekicks, min(3, len(freekicks)))
            for label, info in sorted(fk_clusters.items(), key=lambda x: x[1]['shot_rate'], reverse=True)[:n_top]:
                results.append({
                    'type': 'Freekick', 'cluster_id': int(label), 'frequency': info['count'],
                    'shot_rate': round(info['shot_rate'], 3), 'primary_zone': info['primary_zone'],
                    'swing_type': info['swing_type'], 'avg_target_x': round(info['avg_target_x'], 1),
                    'avg_target_y': round(info['avg_target_y'], 1),
                    'defense_suggestion': self._defense_suggestion(info)
                })
        
        return results
    
    def _defense_suggestion(self, cluster_info: Dict) -> str:
        zone, swing = cluster_info.get('primary_zone', ''), cluster_info.get('swing_type', '')
        suggestions = []
        
        if zone == 'near_post': suggestions.append("니어포스트 존마크 강화")
        elif zone == 'far_post': suggestions.append("파포스트 존 집중")
        elif zone == 'central': suggestions.append("중앙 박스 내 마크 집중")
        elif zone == 'edge_of_box': suggestions.append("박스 가장자리 세컨볼 대비")
        
        if swing == 'inswing': suggestions.append("인스윙 대비 GK 포지셔닝")
        elif swing == 'outswing': suggestions.append("아웃스윙 볼 대응")
        if cluster_info.get('shot_rate', 0) > 0.3: suggestions.append("⚠️ 슈팅 전환률 높음")
        
        return " / ".join(suggestions) if suggestions else "기본 수비 유지"


def team_setpieces(events_df: pd.DataFrame, n_top: int = 2) -> List[Dict]:
    analyzer = SetPieceAnalyzer(events_df)
    return analyzer.top_routines(n_top)
