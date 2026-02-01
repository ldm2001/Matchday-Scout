# 분석 결과 캐시 래퍼
from functools import lru_cache
from typing import Dict, List

from services.data_loader import team_data
from services.pattern_analyzer import team_patterns
from services.setpiece_analyzer import team_setpieces
from services.network_analyzer import team_network, NetworkAnalyzer
from services.vaep_analyzer import team_vaep_summary
from services.vaep_calculator import team_vaep


def _int(value) -> int:
    return int(value)


@lru_cache(maxsize=256)
def pat_cache(team_id: int, n_games: int, n_patterns: int) -> List[Dict]:
    events = team_data(_int(team_id), _int(n_games))
    return team_patterns(events, _int(n_patterns))


@lru_cache(maxsize=256)
def sp_cache(team_id: int, n_games: int, n_top: int) -> List[Dict]:
    events = team_data(_int(team_id), _int(n_games))
    return team_setpieces(events, _int(n_top))


@lru_cache(maxsize=128)
def net_cache(team_id: int, n_games: int, n_hubs: int) -> Dict:
    events = team_data(_int(team_id), _int(n_games))
    return team_network(events, _int(n_hubs))


@lru_cache(maxsize=128)
def graph_cache(team_id: int, n_games: int) -> Dict:
    events = team_data(_int(team_id), _int(n_games))
    analyzer = NetworkAnalyzer(events)
    analyzer.pass_network()
    return analyzer.network_data()


@lru_cache(maxsize=128)
def vaep_sum_cache(team_id: int, n_games: int, n_top: int) -> Dict:
    events = team_data(_int(team_id), _int(n_games))
    return team_vaep_summary(events, _int(n_top))


@lru_cache(maxsize=128)
def vaep_cache(team_id: int, n_games: int) -> Dict:
    events = team_data(_int(team_id), _int(n_games))
    return team_vaep(events, _int(team_id))
