# 분석 결과 캐시 래퍼
from functools import lru_cache
from typing import Dict, List

from services.data_loader import team_data
from services.pattern_analyzer import team_patterns
from services.setpiece_analyzer import team_setpieces
from services.network_analyzer import team_network, NetworkAnalyzer
from services.vaep_analyzer import team_vaep_summary
from services.vaep_calculator import team_vaep


def _to_int(value) -> int:
    return int(value)


@lru_cache(maxsize=256)
def cached_team_patterns(team_id: int, n_games: int, n_patterns: int) -> List[Dict]:
    events = team_data(_to_int(team_id), _to_int(n_games))
    return team_patterns(events, _to_int(n_patterns))


@lru_cache(maxsize=256)
def cached_team_setpieces(team_id: int, n_games: int, n_top: int) -> List[Dict]:
    events = team_data(_to_int(team_id), _to_int(n_games))
    return team_setpieces(events, _to_int(n_top))


@lru_cache(maxsize=128)
def cached_team_network(team_id: int, n_games: int, n_hubs: int) -> Dict:
    events = team_data(_to_int(team_id), _to_int(n_games))
    return team_network(events, _to_int(n_hubs))


@lru_cache(maxsize=128)
def cached_network_graph(team_id: int, n_games: int) -> Dict:
    events = team_data(_to_int(team_id), _to_int(n_games))
    analyzer = NetworkAnalyzer(events)
    analyzer.pass_network()
    return analyzer.network_data()


@lru_cache(maxsize=128)
def cached_team_vaep_summary(team_id: int, n_games: int, n_top: int) -> Dict:
    events = team_data(_to_int(team_id), _to_int(n_games))
    return team_vaep_summary(events, _to_int(n_top))


@lru_cache(maxsize=128)
def cached_team_vaep(team_id: int, n_games: int) -> Dict:
    events = team_data(_to_int(team_id), _to_int(n_games))
    return team_vaep(events, _to_int(team_id))
