'use client';

import { useCallback } from 'react';
import { teamPhases } from '@/lib/api';
import type { Phase } from '@/types';
import { useCancelableQuery } from './useCancelableQuery';

const ANALYSIS_GAMES = 100;

// 팀 공격 페이즈 목록 로더
export function useTeamPhases(teamId: number | null): {
  phases: Phase[];
  loading: boolean;
} {
  const enabled = teamId !== null;
  const fetcher = useCallback(async () => {
    if (teamId === null) return [] as Phase[];
    const res = await teamPhases(teamId, ANALYSIS_GAMES);
    return res.phases as Phase[];
  }, [teamId]);
  const { data, loading } = useCancelableQuery(fetcher, [teamId], { enabled });
  return { phases: data ?? [], loading };
}
