'use client';

import { useCallback } from 'react';
import { teamNetwork } from '@/lib/api';
import type { Hub } from '@/types';
import { useCancelableQuery } from './useCancelableQuery';

const ANALYSIS_GAMES = 100;
const TOP_HUBS = 3;

// 팀 빌드업 허브 로더
export function useTeamHubs(teamId: number | null): {
  hubs: Hub[];
  loading: boolean;
} {
  const enabled = teamId !== null;
  const fetcher = useCallback(async () => {
    if (teamId === null) return [] as Hub[];
    const res = await teamNetwork(teamId, ANALYSIS_GAMES, TOP_HUBS);
    return res.hubs;
  }, [teamId]);
  const { data, loading } = useCancelableQuery(fetcher, [teamId], { enabled });
  return { hubs: data ?? [], loading };
}
