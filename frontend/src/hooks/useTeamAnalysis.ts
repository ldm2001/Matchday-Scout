'use client';

import { useCallback } from 'react';
import { teamAnalysis, TeamAnalysis } from '@/lib/api';
import { useCancelableQuery } from './useCancelableQuery';

const ANALYSIS_GAMES = 100;

// 팀 AI 분석(강점/약점/요약) 로더
export function useTeamAnalysis(teamId: number | null): {
  analysis: TeamAnalysis | null;
  loading: boolean;
} {
  const enabled = teamId !== null;
  const fetcher = useCallback(async () => {
    if (teamId === null) return null;
    return await teamAnalysis(teamId, ANALYSIS_GAMES);
  }, [teamId]);
  const { data, loading } = useCancelableQuery(fetcher, [teamId], { enabled });
  return { analysis: data, loading };
}
