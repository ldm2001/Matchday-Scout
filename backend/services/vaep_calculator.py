# VAEP (Valuing Actions by Estimating Probabilities) 계산기
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
import warnings
warnings.filterwarnings('ignore')


class VAEPCalculator:
    X_ZONES = 6
    Y_ZONES = 5
    ACTION_TYPES = ['Pass', 'Carry', 'Shot', 'Duel', 'Interception', 'Clearance', 'Tackle', 'Foul', 'Cross', 'Throw-in']
    
    def __init__(self, events_df: pd.DataFrame):
        self.events = events_df.copy()
        self.scoring_model = None
        self.conceding_model = None
        self.label_encoder = LabelEncoder()
        self._prepare_data()
    
    # 데이터 전처리
    def _prepare_data(self):
        self.events['leads_to_goal'] = 0
        self.events['leads_to_concede'] = 0
        
        for game_id in self.events['game_id'].unique():
            game_events = self.events[self.events['game_id'] == game_id].copy()
            shots = game_events[game_events['type_name'] == 'Shot']
            goals = shots[shots['result_name'] == 'Goal']
            
            for _, goal in goals.iterrows():
                goal_idx = game_events[game_events['action_id'] == goal['action_id']].index
                if len(goal_idx) > 0:
                    goal_idx = goal_idx[0]
                    team_id = goal['team_id']
                    prev_events = game_events.loc[:goal_idx].tail(10)
                    same_team = prev_events[prev_events['team_id'] == team_id]
                    self.events.loc[same_team.index, 'leads_to_goal'] = 1
                    other_team = prev_events[prev_events['team_id'] != team_id]
                    self.events.loc[other_team.index, 'leads_to_concede'] = 1
    
    # 좌표를 구역 번호로 변환
    def _zone(self, x: float, y: float) -> int:
        if pd.isna(x) or pd.isna(y): return 0
        x_zone = min(int(x / (105 / self.X_ZONES)), self.X_ZONES - 1)
        y_zone = min(int(y / (68 / self.Y_ZONES)), self.Y_ZONES - 1)
        return x_zone * self.Y_ZONES + y_zone
    
    # 액션별 피처 추출
    def _features(self, events: pd.DataFrame) -> pd.DataFrame:
        features = pd.DataFrame()
        features['start_zone'] = events.apply(lambda r: self._zone(r.get('start_x', 0), r.get('start_y', 0)), axis=1)
        features['end_zone'] = events.apply(lambda r: self._zone(r.get('end_x', 0), r.get('end_y', 0)), axis=1)
        
        type_names = events['type_name'].fillna('Unknown')
        type_names = type_names.apply(lambda x: x if x in self.ACTION_TYPES else 'Other')
        all_types = self.ACTION_TYPES + ['Other', 'Unknown']
        self.label_encoder.fit(all_types)
        features['action_type'] = self.label_encoder.transform(type_names)
        features['success'] = (events['result_name'] == 'Successful').astype(int)
        features['distance'] = np.sqrt(events.get('dx', 0)**2 + events.get('dy', 0)**2).fillna(0)
        features['time_normalized'] = events['time_seconds'].fillna(0) / 5400
        features['dist_to_goal'] = np.sqrt((105 - events.get('end_x', 52.5).fillna(52.5))**2 + (34 - events.get('end_y', 34).fillna(34))**2)
        return features.fillna(0)
    
    # 득점/실점 확률 예측 모델 훈련
    def train_models(self):
        features = self._features(self.events)
        self.scoring_model = GradientBoostingClassifier(n_estimators=50, max_depth=4, random_state=42)
        self.scoring_model.fit(features, self.events['leads_to_goal'])
        self.conceding_model = GradientBoostingClassifier(n_estimators=50, max_depth=4, random_state=42)
        self.conceding_model.fit(features, self.events['leads_to_concede'])
        return self
    
    # 각 액션의 VAEP 값 계산
    def action_values(self, team_id: int = None) -> pd.DataFrame:
        if self.scoring_model is None: self.train_models()
        features = self._features(self.events)
        p_score = self.scoring_model.predict_proba(features)[:, 1]
        p_concede = self.conceding_model.predict_proba(features)[:, 1]
        
        results = self.events.copy()
        results['p_score'] = p_score
        results['p_concede'] = p_concede
        results['vaep_offensive'] = results['p_score'].diff().fillna(0)
        results['vaep_defensive'] = -results['p_concede'].diff().fillna(0)
        results['vaep_total'] = results['vaep_offensive'] + results['vaep_defensive']
        return results[results['team_id'] == team_id] if team_id else results
    
    # 선수별 VAEP 레이팅 계산
    def player_ratings(self, team_id: int = None) -> List[Dict]:
        action_values = self.action_values(team_id)
        player_ratings = action_values.groupby(['player_id', 'player_name_ko']).agg({
            'vaep_total': 'sum', 'vaep_offensive': 'sum', 'vaep_defensive': 'sum', 'action_id': 'count'
        }).reset_index()
        player_ratings.columns = ['player_id', 'player_name', 'total_vaep', 'offensive_vaep', 'defensive_vaep', 'actions']
        player_ratings['vaep_per_90'] = player_ratings['total_vaep'] / player_ratings['actions'] * 100
        return player_ratings.sort_values('total_vaep', ascending=False).to_dict('records')
    
    # 가장 가치있는 액션 Top N
    def top_actions(self, team_id: int, n: int = 5) -> List[Dict]:
        action_values = self.action_values(team_id)
        top = action_values.nlargest(n, 'vaep_total')[['player_name_ko', 'type_name', 'vaep_total', 'vaep_offensive', 'start_x', 'start_y', 'end_x', 'end_y']]
        results = []
        for _, row in top.iterrows():
            results.append({
                'player': str(row.get('player_name_ko', 'Unknown')),
                'action': str(row.get('type_name', 'Unknown')),
                'value': round(float(row.get('vaep_total', 0)), 4),
                'offensive_value': round(float(row.get('vaep_offensive', 0)), 4),
                'start_x': float(row.get('start_x', 0) or 0), 'start_y': float(row.get('start_y', 0) or 0),
                'end_x': float(row.get('end_x', 0) or 0), 'end_y': float(row.get('end_y', 0) or 0)
            })
        return results


def team_vaep(events_df: pd.DataFrame, team_id: int) -> Dict:
    calculator = VAEPCalculator(events_df)
    calculator.train_models()
    ratings = calculator.player_ratings(team_id)
    top = calculator.top_actions(team_id, 5)
    total = sum(p.get('total_vaep', 0) for p in ratings)
    offensive = sum(p.get('offensive_vaep', 0) for p in ratings)
    defensive = sum(p.get('defensive_vaep', 0) for p in ratings)
    return {
        'team_id': team_id, 'total_vaep': round(total, 3),
        'offensive_vaep': round(offensive, 3), 'defensive_vaep': round(defensive, 3),
        'player_ratings': ratings[:10], 'top_valuable_actions': top
    }
