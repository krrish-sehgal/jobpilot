"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import type { User } from "@/lib/api/types";
import { clearToken, getToken, onSessionLost, setToken } from "./token";

type Status = "loading" | "authenticated" | "anonymous";

interface AuthValue {
  status: Status;
  user: User | null;
  requestCode: (email: string) => Promise<void>;
  verifyCode: (email: string, code: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

/**
 * Owns "who is signed in". On mount it trusts a stored token only after
 * `GET /me` confirms it, so a stale token can't flash the app UI.
 * Any 401 anywhere (see http.ts -> clearToken) flips us to anonymous, and the
 * route guard does the redirect.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (!getToken()) {
      setStatus("anonymous");
      return;
    }
    let cancelled = false;
    api
      .me()
      .then((u) => {
        if (cancelled) return;
        setUser(u);
        setStatus("authenticated");
      })
      .catch(() => {
        if (cancelled) return;
        clearToken(false);
        setStatus("anonymous");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(
    () =>
      onSessionLost(() => {
        setUser(null);
        setStatus("anonymous");
      }),
    [],
  );

  const requestCode = useCallback((email: string) => api.requestCode(email), []);

  const verifyCode = useCallback(async (email: string, code: string) => {
    const session = await api.verifyCode(email, code);
    setToken(session.access_token, session.expires_at);
    setUser(session.user);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(() => {
    clearToken(false);
    setUser(null);
    setStatus("anonymous");
  }, []);

  const value = useMemo(() => ({ status, user, requestCode, verifyCode, logout }), [status, user, requestCode, verifyCode, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
