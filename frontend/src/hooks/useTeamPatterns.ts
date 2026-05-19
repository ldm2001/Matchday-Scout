'use client';

import { useCallback } from 'react';
import { teamPatterns } from '@/lib/api';
import type { Pattern } from '@/types';
import { useCancelableQuery } from './useCancelableQuery';

const ANALYSIS_GAMES = 100;
const TOP_PATTERNS = 5;

// 팀 공격 패턴 로더 (TOP N)
export function useTeamPatterns(teamId: number | null): {
  patterns: Pattern[];
  loading: boolean;
} {
  const enabled = teamId !== null;
  const fetcher = useCallback(async () => {
    if (teamId === null) return [] as Pattern[];
    const res = await teamPatterns(teamId, ANALYSIS_GAMES, TOP_PATTERNS);
    return res.patterns;
  }, [teamId]);
  const { data, loading } = useCancelableQuery(fetcher, [teamId], { enabled });
  return { patterns: data ?? [], loading };
}
