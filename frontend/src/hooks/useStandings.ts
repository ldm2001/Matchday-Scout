'use client';

import { useCallback } from 'react';
import { teamsOverview } from '@/lib/api';
import type { TeamStanding } from '@/types';
import { useCancelableQuery } from './useCancelableQuery';

// 사이드바 팀 순위 로더
export function useStandings(): { standings: TeamStanding[]; loading: boolean } {
  const fetcher = useCallback(async () => {
    const res = await teamsOverview();
    return res.standings as TeamStanding[];
  }, []);
  const { data, loading } = useCancelableQuery(fetcher, []);
  return { standings: data ?? [], loading };
}
