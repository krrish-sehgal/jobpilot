"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { describeError } from "@/lib/api/errors";
import type { ResumeSummary } from "@/lib/api/types";

/** The user's uploaded resumes, newest first, plus the "make primary" action. */
export function useResumes() {
  const [resumes, setResumes] = useState<ResumeSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setResumes(await api.listResumes());
      setError(null);
    } catch (e) {
      setError(describeError(e));
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const makePrimary = useCallback(async (id: string) => {
    // Optimistic: flip locally, then reconcile with the server.
    setResumes((prev) => prev?.map((r) => ({ ...r, is_primary: r.id === id })) ?? prev);
    try {
      await api.makePrimary(id);
    } catch (e) {
      setError(describeError(e));
    } finally {
      await refresh();
    }
  }, [refresh]);

  return { resumes, error, refresh, makePrimary };
}
