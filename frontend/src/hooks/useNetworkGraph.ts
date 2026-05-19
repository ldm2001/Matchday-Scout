'use client';

import { useCallback } from 'react';
import { netGraph } from '@/lib/api';
import type { NetworkGraph } from '@/types';
import { useCancelableQuery } from './useCancelableQuery';

const ANALYSIS_GAMES = 100;

// 패스 네트워크 그래프 로더
export function useNetworkGraph(teamId: number | null): {
  graph: NetworkGraph | null;
  loading: boolean;
} {
  const enabled = teamId !== null;
  const fetcher = useCallback(async () => {
    if (teamId === null) return null as NetworkGraph | null;
    const res = await netGraph(teamId, ANALYSIS_GAMES);
    return res.graph;
  }, [teamId]);
  const { data, loading } = useCancelableQuery(fetcher, [teamId], { enabled });
  return { graph: data, loading };
}
