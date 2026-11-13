"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { describeError } from "@/lib/api/errors";

interface PollOptions<T> {
  intervalMs: number;
  /** Stop polling when this returns true for the latest result. */
  isDone: (value: T) => boolean;
  /** Polling is paused while false (e.g. before we have an id). */
  enabled?: boolean;
  /** Give up after this many failures in a row. */
  maxConsecutiveErrors?: number;
}

/**
 * Calls `fetcher` immediately, then every `intervalMs` until `isDone`.
 * Chained setTimeouts (not setInterval) so a slow response can never overlap
 * the next request. Transient errors are tolerated; `retry()` restarts.
 * Used for resume parsing and tailoring, which the contract says to poll.
 */
export function usePolling<T>(fetcher: () => Promise<T>, { intervalMs, isDone, enabled = true, maxConsecutiveErrors = 3 }: PollOptions<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  // Keep the latest callbacks in refs so callers can pass inline functions without restarting the loop.
  const fetchRef = useRef(fetcher);
  const doneRef = useRef(isDone);
  fetchRef.current = fetcher;
  doneRef.current = isDone;

  useEffect(() => {
    if (!enabled) return;
    // A fresh run must not show the previous run's result or error (e.g. a stale failure from the last upload).
    setData(null);
    setError(null);
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    let failures = 0;

    const tick = async () => {
      try {
        const value = await fetchRef.current();
        if (cancelled) return;
        failures = 0;
        setError(null);
        setData(value);
        if (!doneRef.current(value)) timer = setTimeout(tick, intervalMs);
      } catch (e) {
        if (cancelled) return;
        failures += 1;
        if (failures >= maxConsecutiveErrors) setError(describeError(e));
        else timer = setTimeout(tick, intervalMs * 2);
      }
    };
    void tick();

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [enabled, intervalMs, maxConsecutiveErrors, nonce]);

  const retry = useCallback(() => {
    setError(null);
    setNonce((n) => n + 1);
  }, []);

  return { data, error, retry };
}
