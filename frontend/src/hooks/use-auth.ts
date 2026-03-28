"use client";

import { useState, useCallback, useSyncExternalStore } from "react";
import { api, toErrorMessage } from "@/lib/api-client";
import { setToken, clearToken, getToken } from "@/lib/auth";
import { getWorkspaceId, setWorkspaceId } from "@/lib/workspace";

function subscribe(cb: () => void) {
  window.addEventListener("storage", cb);
  return () => window.removeEventListener("storage", cb);
}

function getSnapshot() {
  return !!getToken();
}

export function useAuth() {
  const isAuthed = useSyncExternalStore(subscribe, getSnapshot, () => false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = useCallback(async (email: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const { access_token } = await api.login(email, password);
      setToken(access_token);
      // Do not await: a slow or stuck /workspaces call must not block login + redirect.
      void (async () => {
        try {
          const workspaces = await api.listWorkspaces();
          if (workspaces.length && !getWorkspaceId()) {
            setWorkspaceId(workspaces[0].id);
          }
        } catch {
          /* workspace list optional on first login */
        }
      })();
      return { ok: true as const };
    } catch (err) {
      const msg = toErrorMessage(err);
      setError(msg);
      return { ok: false as const, error: msg };
    } finally {
      setLoading(false);
    }
  }, []);

  const register = useCallback(
    async (email: string, password: string, fullName?: string) => {
      setLoading(true);
      setError(null);
      try {
        await api.register(email, password, fullName);
        return { ok: true as const };
      } catch (err) {
        const msg = toErrorMessage(err);
        setError(msg);
        return { ok: false as const, error: msg };
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const logout = useCallback(() => {
    clearToken();
    window.location.assign("/login");
  }, []);

  return { isAuthed, loading, error, login, register, logout };
}
