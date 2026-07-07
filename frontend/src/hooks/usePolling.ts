import { useEffect, useState, useRef, useCallback } from "react";

export function usePolling<T>(
  fetchFn: () => Promise<T>,
  interval: number = 5000,
  immediate: boolean = true
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 使用 useCallback 包装 fetch 函数，避免依赖变化
  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await fetchFn();
      setData(result);
    } catch (err) {
      setError(err as Error);
    } finally {
      setLoading(false);
    }
  }, [fetchFn]);

  const startPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
    if (immediate) {
      fetch();
    }
    intervalRef.current = setInterval(fetch, interval);
  }, [fetch, interval, immediate]);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    startPolling();
    return stopPolling;
  }, [startPolling, stopPolling]);

  return { data, loading, error, refetch: fetch, startPolling, stopPolling };
}
