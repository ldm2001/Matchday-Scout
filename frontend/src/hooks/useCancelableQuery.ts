'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

type Options = {
  enabled?: boolean;
};

type QueryResult<T> = {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refresh: () => void;
};

// page.tsx의 analysisToken/simToken 패턴을 일반화
// 토큰 ref로 응답 순서 불일치(race)를 방지하고, 언마운트 시 setState를 차단한다.
export function useCancelableQuery<T>(
  fetcher: () => Promise<T>,
  deps: readonly unknown[],
  options: Options = {},
): QueryResult<T> {
  const { enabled = true } = options;
  const [data, setData] = useState<T | null>(null);
  // enabled=true이면 useEffect가 곧바로 fetch를 발화하므로 첫 렌더부터 loading=true로 둔다
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<Error | null>(null);
  const tokenRef = useRef(0);
  const [refreshTick, setRefreshTick] = useState(0);

  const refresh = useCallback(() => setRefreshTick((n) => n + 1), []);

  useEffect(() => {
    if (!enabled) {
      tokenRef.current += 1;
      setData(null);
      setLoading(false);
      setError(null);
      return;
    }
    const token = ++tokenRef.current;
    let alive = true;
    setLoading(true);
    setData(null);
    setError(null);
    fetcher()
      .then((result) => {
        if (alive && token === tokenRef.current) setData(result);
      })
      .catch((err: unknown) => {
        if (alive && token === tokenRef.current) {
          const e = err instanceof Error ? err : new Error(String(err));
          console.error(e);
          setError(e);
        }
      })
      .finally(() => {
        if (alive && token === tokenRef.current) setLoading(false);
      });
    return () => {
      alive = false;
    };
    // fetcher는 매 렌더 재생성될 수 있으므로 deps로 제어한다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled, refreshTick]);

  return { data, loading, error, refresh };
}
