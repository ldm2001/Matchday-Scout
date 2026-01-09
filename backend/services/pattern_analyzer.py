# Phase 분할 및 패턴 분석
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from collections import Counter
from typing import List, Dict


class PhaseAnalyzer:
    PHASE_GAP_SECONDS = 10
    MIN_PHASE_EVENTS = 3
    
    def __init__(self, events_df: pd.DataFrame):
        self.events = events_df.sort_values(['game_id', 'period_id', 'time_seconds'])
        
    def split_phases(self) -> List[pd.DataFrame]:
        phases = []
        
        for game_id in self.events['game_id'].unique():
            game_events = self.events[self.events['game_id'] == game_id]
            
            for period_id in game_events['period_id'].unique():
                period_events = game_events[game_events['period_id'] == period_id].reset_index(drop=True)
                if len(period_events) < self.MIN_PHASE_EVENTS:
                    continue
                    
                current_phase = []
                prev_time, prev_team = None, None
                
                for idx, row in period_events.iterrows():
                    curr_time, curr_team = row['time_seconds'], row['team_id']
                    new_phase = False
                    
                    if prev_time is not None:
                        if curr_time - prev_time > self.PHASE_GAP_SECONDS:
                            new_phase = True
                        elif prev_team != curr_team and row['type_name'] in ['Interception', 'Recovery', 'Tackle', 'Clearance']:
                            new_phase = True
                    
                    if new_phase and len(current_phase) >= self.MIN_PHASE_EVENTS:
                        phases.append(pd.DataFrame(current_phase))
                        current_phase = []
                    
                    current_phase.append(row)
                    prev_time, prev_team = curr_time, curr_team
                
                if len(current_phase) >= self.MIN_PHASE_EVENTS:
                    phases.append(pd.DataFrame(current_phase))
        
        return phases
    
    def phase_features(self, phase: pd.DataFrame) -> Dict:
        features = {
            'length': len(phase),
            'duration': phase['time_seconds'].max() - phase['time_seconds'].min(),
            'start_x': phase.iloc[0].get('start_x', 0),
            'start_y': phase.iloc[0].get('start_y', 0),
            'end_x': phase.iloc[-1].get('end_x', 0),
            'end_y': phase.iloc[-1].get('end_y', 0),
            'avg_x': phase['start_x'].mean() if 'start_x' in phase.columns else 0,
            'avg_y': phase['start_y'].mean() if 'start_y' in phase.columns else 0,
            'pass_count': len(phase[phase['type_name'] == 'Pass']),
            'carry_count': len(phase[phase['type_name'] == 'Carry']),
            'shot_count': len(phase[phase['type_name'] == 'Shot']),
            'cross_count': len(phase[phase['type_name'] == 'Cross']),
            'forward_progress': phase['dx'].sum() if 'dx' in phase.columns else 0,
            'lateral_movement': abs(phase['dy']).sum() if 'dy' in phase.columns else 0,
            'event_sequence': '_'.join(phase['type_name'].tolist())
        }
        
        if 'result_name' in phase.columns:
            results = phase['result_name'].value_counts()
            total = len(phase[phase['result_name'].notna()])
            features['success_rate'] = results.get('Successful', 0) / total if total > 0 else 0
        
        return features
    
    def _pitch_zone(self, x: float, y: float) -> str:
        x_zone = "수비" if x < 35 else ("중앙" if x < 70 else "공격")
        y_zone = "좌측" if y < 22.67 else ("중앙" if y < 45.33 else "우측")
        return f"{x_zone}_{y_zone}"


class PatternMiner:
    def __init__(self, phases: List[pd.DataFrame]):
        self.phases = phases
        self.phase_features = []
        
    def _phase_features(self, phase: pd.DataFrame) -> Dict:
        features = {
            'length': len(phase),
            'duration': phase['time_seconds'].max() - phase['time_seconds'].min() if len(phase) > 0 else 0,
            'start_x': phase.iloc[0].get('start_x', 0) if len(phase) > 0 else 0,
            'start_y': phase.iloc[0].get('start_y', 0) if len(phase) > 0 else 0,
            'end_x': phase.iloc[-1].get('end_x', 0) if len(phase) > 0 else 0,
            'end_y': phase.iloc[-1].get('end_y', 0) if len(phase) > 0 else 0,
            'avg_x': phase['start_x'].mean() if 'start_x' in phase.columns else 0,
            'avg_y': phase['start_y'].mean() if 'start_y' in phase.columns else 0,
            'pass_count': len(phase[phase['type_name'] == 'Pass']) if 'type_name' in phase.columns else 0,
            'carry_count': len(phase[phase['type_name'] == 'Carry']) if 'type_name' in phase.columns else 0,
            'shot_count': len(phase[phase['type_name'] == 'Shot']) if 'type_name' in phase.columns else 0,
            'cross_count': len(phase[phase['type_name'] == 'Cross']) if 'type_name' in phase.columns else 0,
            'forward_progress': phase['dx'].sum() if 'dx' in phase.columns else 0,
            'lateral_movement': abs(phase['dy']).sum() if 'dy' in phase.columns else 0,
            'event_sequence': '_'.join(phase['type_name'].tolist()) if 'type_name' in phase.columns else '',
        }
        
        if 'result_name' in phase.columns:
            results = phase['result_name'].value_counts()
            total = len(phase[phase['result_name'].notna()])
            features['success_rate'] = results.get('Successful', 0) / total if total > 0 else 0
        
        return features
        
    def extract_all(self):
        self.phase_features = []
        for i, phase in enumerate(self.phases):
            features = self._phase_features(phase)
            features['phase_id'] = i
            self.phase_features.append(features)
        return self.phase_features
    
    def cluster(self, n_clusters: int = 5) -> Dict:
        if not self.phase_features:
            self.extract_all()
        
        feature_cols = ['length', 'duration', 'start_x', 'start_y', 'end_x', 'end_y',
                        'avg_x', 'avg_y', 'pass_count', 'carry_count', 
                        'forward_progress', 'lateral_movement']
        
        X = np.array([[f.get(col, 0) for col in feature_cols] for f in self.phase_features])
        X_scaled = StandardScaler().fit_transform(X)
        labels = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit_predict(X_scaled)
        
        clusters = {}
        for i, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = {'phases': [], 'count': 0, 'shot_phases': 0, 'avg_features': {}}
            clusters[label]['phases'].append(i)
            clusters[label]['count'] += 1
            if self.phase_features[i].get('shot_count', 0) > 0:
                clusters[label]['shot_phases'] += 1
        
        for label in clusters:
            phase_indices = clusters[label]['phases']
            for col in feature_cols:
                clusters[label]['avg_features'][col] = np.mean([self.phase_features[i].get(col, 0) for i in phase_indices])
            clusters[label]['shot_conversion_rate'] = clusters[label]['shot_phases'] / clusters[label]['count']
        
        return clusters
    
    def top_patterns(self, n_top: int = 3) -> List[Dict]:
        clusters = self.cluster()
        sorted_clusters = sorted(clusters.items(), key=lambda x: x[1]['shot_conversion_rate'], reverse=True)
        
        patterns = []
        for label, info in sorted_clusters[:n_top]:
            sequences = [self.phase_features[i]['event_sequence'] for i in info['phases']]
            common = self._common_ngrams(sequences)
            
            patterns.append({
                'cluster_id': int(label),
                'frequency': info['count'],
                'shot_conversion_rate': round(info['shot_conversion_rate'], 3),
                'avg_duration': round(info['avg_features'].get('duration', 0), 1),
                'avg_passes': round(info['avg_features'].get('pass_count', 0), 1),
                'avg_forward_progress': round(info['avg_features'].get('forward_progress', 0), 1),
                'avg_start_zone': self._pitch_zone(info['avg_features'].get('start_x', 0), info['avg_features'].get('start_y', 0)),
                'avg_end_zone': self._pitch_zone(info['avg_features'].get('end_x', 0), info['avg_features'].get('end_y', 0)),
                'common_sequences': common[:3]
            })
        
        return patterns
    
    def _common_ngrams(self, sequences: List[str], n: int = 3) -> List[str]:
        ngram_counter = Counter()
        for seq in sequences:
            events = seq.split('_')
            for i in range(len(events) - n + 1):
                ngram_counter['_'.join(events[i:i+n])] += 1
        return [ngram for ngram, _ in ngram_counter.most_common(5)]
    
    def _pitch_zone(self, x: float, y: float) -> str:
        x_zone = "수비" if x < 35 else ("중앙" if x < 70 else "공격")
        y_zone = "좌측" if y < 22.67 else ("중앙" if y < 45.33 else "우측")
        return f"{x_zone}_{y_zone}"


def team_patterns(events_df: pd.DataFrame, n_patterns: int = 3) -> List[Dict]:
    analyzer = PhaseAnalyzer(events_df)
    phases = analyzer.split_phases()
    if not phases:
        return []
    miner = PatternMiner(phases)
    return miner.top_patterns(n_patterns)
