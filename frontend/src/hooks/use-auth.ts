"use client";

import { useState, useCallback, useSyncExternalStore } from "react";
import { api, toErrorMessage } from "@/lib/api-client";
import { setToken, clearToken, getToken } from "@/lib/auth";

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
      return true;
    } catch (err) {
      setError(toErrorMessage(err));
      return false;
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
        return true;
      } catch (err) {
        setError(toErrorMessage(err));
        return false;
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
