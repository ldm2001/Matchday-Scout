'use client';

import { useCallback, useRef, useState } from 'react';
import { matchChances, type ChanceAnalysis } from '@/lib/api';

interface ChanceAnalysisState {
  selectedMatch: number | null;
  chanceAnalysis: ChanceAnalysis | null;
  loading: boolean;
  load: (gameId: number) => void;
  reset: () => void;
}

// 놓친 찬스 분석 로더 — 토큰 기반 race 방지 + 명령형 load/reset
export function useChanceAnalysis(): ChanceAnalysisState {
  const [selectedMatch, setSelectedMatch] = useState<number | null>(null);
  const [chanceAnalysis, setChanceAnalysis] = useState<ChanceAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const tokenRef = useRef(0);

  const load = useCallback((gameId: number) => {
    const token = ++tokenRef.current;
    setSelectedMatch(gameId);
    setChanceAnalysis(null);
    setLoading(true);
    matchChances(gameId)
      .then((data) => {
        if (tokenRef.current === token) setChanceAnalysis(data);
      })
      .catch((err) => {
        if (tokenRef.current === token) console.error('Failed to load chance analysis:', err);
      })
      .finally(() => {
        if (tokenRef.current === token) setLoading(false);
      });
  }, []);

  const reset = useCallback(() => {
    tokenRef.current += 1;
    setSelectedMatch(null);
    setChanceAnalysis(null);
    setLoading(false);
  }, []);

  return { selectedMatch, chanceAnalysis, loading, load, reset };
}
