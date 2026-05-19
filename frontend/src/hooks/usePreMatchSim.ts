'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { preMatch } from '@/lib/api';
import type { SimResult, TeamStanding } from '@/types';

const ANALYSIS_GAMES = 100;

// 모듈 스코프 캐시 — 탭 재진입 간 결과 유지
const resultCache: Record<string, SimResult> = {};

interface PreMatchSimState {
  result: SimResult | null;
  loading: boolean;
  isStale: boolean;
  key: string | null;
  run: () => void;
}

// 프리매치 시뮬레이션 로더 — 자동 실행 + 모듈 캐시 + isStale 플래그
export function usePreMatchSim(
  ourTeam: TeamStanding | null,
  opponent: TeamStanding | null,
): PreMatchSimState {
  const key = ourTeam && opponent ? `${ourTeam.team_id}-${opponent.team_id}` : null;
  const initialCached = key ? (resultCache[key] ?? null) : null;
  const [result, setResult] = useState<SimResult | null>(initialCached);
  const [dataKey, setDataKey] = useState<string | null>(initialCached ? key : null);
  const [loading, setLoading] = useState(false);
  const [trackedKey, setTrackedKey] = useState<string | null>(key);
  const tokenRef = useRef(0);
  const ranKeyRef = useRef<string | null>(initialCached ? key : null);

  // 키 변경 시 캐시 동기화는 렌더 중 처리 (순수 파생, 외부 호출 없음)
  if (trackedKey !== key) {
    setTrackedKey(key);
    if (!key) {
      setResult(null);
      setDataKey(null);
    } else {
      const cached = resultCache[key];
      if (cached) {
        setResult(cached);
        setDataKey(key);
      }
    }
  }

  const run = useCallback(() => {
    if (!ourTeam || !opponent) return;
    const k = `${ourTeam.team_id}-${opponent.team_id}`;
    const token = ++tokenRef.current;
    setLoading(true);
    preMatch(ourTeam.team_id, opponent.team_id, ANALYSIS_GAMES)
      .then((data) => {
        if (tokenRef.current !== token) return;
        resultCache[k] = data;
        setResult(data);
        setDataKey(k);
      })
      .catch((err) => {
        if (tokenRef.current === token) console.error('Simulation failed:', err);
      })
      .finally(() => {
        if (tokenRef.current === token) setLoading(false);
      });
  }, [ourTeam, opponent]);

  // 캐시 미스 시 자동 실행 — 순수 imperative 트리거 (ref 변경 + run 호출만)
  useEffect(() => {
    if (!key) {
      tokenRef.current += 1;
      ranKeyRef.current = null;
      return;
    }
    if (resultCache[key]) {
      ranKeyRef.current = key;
      return;
    }
    if (ranKeyRef.current === key) return;
    ranKeyRef.current = key;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    run();
  }, [key, run]);

  const isStale = Boolean(result && key && dataKey !== key);

  return { result, loading, isStale, key, run };
}
