'use client';

import { useCallback } from 'react';
import { matchList, type MatchResult } from '@/lib/api';
import { useCancelableQuery } from './useCancelableQuery';

// 팀 최근 경기 목록 로더
export function useRecentMatches(teamId: number | null): {
  matches: MatchResult[];
  loading: boolean;
} {
  const enabled = teamId !== null;
  const fetcher = useCallback(async () => {
    if (teamId === null) return [] as MatchResult[];
    const data = await matchList(teamId);
    return data.matches;
  }, [teamId]);
  const { data, loading } = useCancelableQuery(fetcher, [teamId], { enabled });
  return { matches: data ?? [], loading };
}
