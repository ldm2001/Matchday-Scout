'use client';

import { useCallback } from 'react';
import { teamSetpieces } from '@/lib/api';
import type { SetPieceRoutine } from '@/types';
import { useCancelableQuery } from './useCancelableQuery';

const ANALYSIS_GAMES = 100;

// 팀 세트피스 루틴 로더 (corner/free kick)
export function useTeamSetpieces(teamId: number | null): {
  setpieces: SetPieceRoutine[];
  loading: boolean;
} {
  const enabled = teamId !== null;
  const fetcher = useCallback(async () => {
    if (teamId === null) return [] as SetPieceRoutine[];
    const res = await teamSetpieces(teamId, ANALYSIS_GAMES);
    return res.routines as SetPieceRoutine[];
  }, [teamId]);
  const { data, loading } = useCancelableQuery(fetcher, [teamId], { enabled });
  return { setpieces: data ?? [], loading };
}
