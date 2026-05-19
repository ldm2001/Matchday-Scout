'use client';

import { useCallback } from 'react';
import { teamVAEP, VAEPSummary } from '@/lib/api';
import { useCancelableQuery } from './useCancelableQuery';

const ANALYSIS_GAMES = 100;

// 팀 VAEP(공헌도) 로더
export function useTeamVAEP(teamId: number | null): {
  vaep: VAEPSummary | null;
  loading: boolean;
} {
  const enabled = teamId !== null;
  const fetcher = useCallback(async () => {
    if (teamId === null) return null as VAEPSummary | null;
    return await teamVAEP(teamId, ANALYSIS_GAMES);
  }, [teamId]);
  const { data, loading } = useCancelableQuery(fetcher, [teamId], { enabled });
  return { vaep: data, loading };
}
