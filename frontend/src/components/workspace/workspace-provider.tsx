"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, toErrorMessage, type WorkspaceOut } from "@/lib/api-client";
import { toast } from "sonner";
import { getWorkspaceId, setWorkspaceId } from "@/lib/workspace";

export interface WorkspaceContextValue {
  workspaces: WorkspaceOut[];
  /** Выбранное пространство после синхронизации с localStorage и списком API */
  currentWorkspace: WorkspaceOut | null;
  loading: boolean;
  error: string | null;
  /** Сохранённый id отсутствует в списке (исправлено на первый доступный) */
  hadStaleSelection: boolean;
  refresh: () => Promise<void>;
  selectWorkspace: (id: string) => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [workspaces, setWorkspaces] = useState<WorkspaceOut[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hadStaleSelection, setHadStaleSelection] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const w = await api.listWorkspaces();
      setWorkspaces(w);
      let id = getWorkspaceId() ?? "";
      let stale = false;
      if (w.length === 0) {
        setActiveId(null);
        setHadStaleSelection(false);
        return;
      }
      if (!id || !w.some((x) => x.id === id)) {
        stale = !!id;
        id = w[0].id;
        setWorkspaceId(id);
      }
      setHadStaleSelection(stale);
      setActiveId(id);
    } catch (err) {
      const msg = toErrorMessage(err);
      setError(msg);
      toast.error(msg);
      setWorkspaces([]);
      setActiveId(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const selectWorkspace = useCallback((id: string) => {
    setWorkspaceId(id);
    setActiveId(id);
    window.location.reload();
  }, []);

  const currentWorkspace = useMemo(() => {
    if (!activeId) return null;
    return workspaces.find((x) => x.id === activeId) ?? null;
  }, [workspaces, activeId]);

  const value = useMemo(
    () => ({
      workspaces,
      currentWorkspace,
      loading,
      error,
      hadStaleSelection,
      refresh,
      selectWorkspace,
    }),
    [workspaces, currentWorkspace, loading, error, hadStaleSelection, refresh, selectWorkspace]
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) {
    throw new Error("useWorkspace must be used within WorkspaceProvider");
  }
  return ctx;
}
