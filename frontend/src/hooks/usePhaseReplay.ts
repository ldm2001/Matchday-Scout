'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { phaseReplay } from '@/lib/api';
import type { ReplayEvent } from '@/types';

const ANALYSIS_GAMES = 100;

interface PhaseReplayState {
  events: ReplayEvent[];
  selectedPhaseId: number | null;
  loading: boolean;
  loadReplay: (phaseId: number) => Promise<void>;
}

// 공격 페이즈 리플레이 로더 (imperative trigger)
export function usePhaseReplay(teamId: number | null): PhaseReplayState {
  const [events, setEvents] = useState<ReplayEvent[]>([]);
  const [selectedPhaseId, setSelectedPhaseId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const tokenRef = useRef(0);

  // 팀 전환 시 리셋
  useEffect(() => {
    tokenRef.current += 1;
    setEvents([]);
    setSelectedPhaseId(null);
    setLoading(false);
  }, [teamId]);

  const loadReplay = useCallback(
    async (phaseId: number) => {
      if (teamId === null) return;
      const token = ++tokenRef.current;
      setLoading(true);
      try {
        const data = await phaseReplay(teamId, phaseId, ANALYSIS_GAMES);
        if (tokenRef.current !== token) return;
        setEvents(data.events);
        setSelectedPhaseId(phaseId);
      } catch (err) {
        if (tokenRef.current === token) console.error('Failed to load replay:', err);
      } finally {
        if (tokenRef.current === token) setLoading(false);
      }
    },
    [teamId],
  );

  return { events, selectedPhaseId, loading, loadReplay };
}
