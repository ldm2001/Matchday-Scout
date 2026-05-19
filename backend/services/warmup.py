# 스타트업 prewarm 퍼사드 - 라우터 레이어가 data/model을 직접 import하지 않도록 격리
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable

from .analyzers.network import net_box
from .analyzers.pattern import pat_box
from .analyzers.setpiece import set_box
from .analyzers.team import note_box
from .core.data import data_mark, matches, raw
from .vaep.model import sum_box, vaep_models

_LOG = logging.getLogger(__name__)


# CatBoost/pandas는 GIL을 자주 풀어 ThreadPool 효과 - n_games/top_k는 page.tsx 디폴트와 동일
def warm_all(n_games: int = 100, top_k: int = 10) -> None:
    """raw/matches/vaep_models 1회 적재 후 팀별 note/sum/pat/set/net 캐시를 병렬 예열한다."""
    try:
        raw()
        match_df = matches()
        vaep_models()
        mark = data_mark()
        team_ids = sorted({
            *match_df["home_team_id"].dropna().astype(int).tolist(),
            *match_df["away_team_id"].dropna().astype(int).tolist(),
        })
    except Exception as exc:
        _LOG.warning("prewarm 부트스트랩 실패: %s", exc)
        return

    _warm_teams(team_ids, n_games=n_games, top_k=top_k, mark=mark)


def _warm_teams(team_ids: Iterable[int], *, n_games: int, top_k: int, mark: tuple) -> None:
    team_ids = [int(tid) for tid in team_ids]
    if not team_ids:
        return

    def _warm_one(tid: int) -> None:
        # note_box 내부에서 pat_box(., 5, mark)/set_box(., 4, mark)/net_box(., 3, mark)이 함께 데워짐
        try:
            note_box(tid, n_games, mark)
        except Exception as exc:
            _LOG.warning("note_box prewarm 실패 team=%s: %s", tid, exc)
        try:
            sum_box(tid, n_games, top_k, mark)
        except Exception as exc:
            _LOG.warning("sum_box prewarm 실패 team=%s: %s", tid, exc)
        # 라우터 기본값(n_games=5, top_k=3/2/2) 캐시를 미리 채워 첫 요청 지연 제거
        try:
            pat_box(tid, 5, 3, mark)
        except Exception as exc:
            _LOG.warning("pat_box prewarm 실패 team=%s: %s", tid, exc)
        try:
            set_box(tid, 5, 2, mark)
        except Exception as exc:
            _LOG.warning("set_box prewarm 실패 team=%s: %s", tid, exc)
        try:
            net_box(tid, 5, 2, mark)
        except Exception as exc:
            _LOG.warning("net_box prewarm 실패 team=%s: %s", tid, exc)

    workers = min(8, max(2, len(team_ids)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="prewarm") as pool:
        for _ in pool.map(_warm_one, team_ids):
            pass
