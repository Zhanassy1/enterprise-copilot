"use client";

import { useState, useCallback, useSyncExternalStore } from "react";
import { api, toErrorMessage, type Token as ApiToken, type UserOut } from "@/lib/api-client";
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

  const login = useCallback(
    async (
      email: string,
      password: string,
      inviteToken?: string | null
    ): Promise<{ ok: true } | { ok: false; error: string }> => {
      setLoading(true);
      setError(null);
      try {
        const { access_token } = await api.login(email, password, inviteToken ?? null);
        setToken(access_token);
        try {
          const workspaces = await api.listWorkspaces();
          if (workspaces.length && !getWorkspaceId()) {
            setWorkspaceId(workspaces[0].id);
          }
        } catch {
          /* workspace list optional on first login */
        }
        return { ok: true };
      } catch (err) {
        const msg = toErrorMessage(err);
        setError(msg);
        return { ok: false, error: msg };
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const register = useCallback(
    async (
      email: string,
      password: string,
      fullName?: string,
      inviteToken?: string | null
    ): Promise<{ ok: true } | { ok: false; error: string }> => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.register(email, password, fullName, inviteToken ?? null);
        function isToken(r: UserOut | ApiToken): r is ApiToken {
          return typeof (r as ApiToken).access_token === "string";
        }
        if (isToken(res)) {
          setToken(res.access_token);
          try {
            const workspaces = await api.listWorkspaces();
            if (workspaces.length && !getWorkspaceId()) {
              setWorkspaceId(workspaces[0].id);
            }
          } catch {
            /* optional */
          }
        }
        return { ok: true };
      } catch (err) {
        const msg = toErrorMessage(err);
        setError(msg);
        return { ok: false, error: msg };
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
