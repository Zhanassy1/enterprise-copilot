"use client";

import { useEffect, useState } from "react";
import { api, type WorkspaceOut } from "@/lib/api-client";
import { getWorkspaceId, setWorkspaceId } from "@/lib/workspace";
import { workspaceRoleLabel } from "@/lib/product-terminology";
import { Skeleton } from "@/components/ui/skeleton";

export function WorkspaceSwitcher() {
  const [list, setList] = useState<WorkspaceOut[]>([]);
  const [current, setCurrent] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setCurrent(getWorkspaceId() ?? "");
    setLoading(true);
    setError(null);
    void api
      .listWorkspaces()
      .then((w) => {
        setList(w);
        if (w.length && !getWorkspaceId()) {
          setWorkspaceId(w[0].id);
          setCurrent(w[0].id);
        }
      })
      .catch(() => {
        setError("Не удалось загрузить workspace");
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="mb-2 px-3">
        <p className="mb-1 text-xs text-muted-foreground">Рабочее пространство</p>
        <Skeleton className="h-10 w-full rounded-md" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mb-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
        {error}
      </div>
    );
  }

  if (list.length === 0) {
    return (
      <div className="mb-2 px-3 text-xs text-muted-foreground">
        Нет доступных workspace. Обратитесь к администратору или создайте организацию (когда будет доступно в продукте).
      </div>
    );
  }

  return (
    <label className="mb-2 block px-3 text-xs text-muted-foreground">
      Рабочее пространство
      <select
        className="mt-1 w-full rounded-md border border-input bg-background px-2 py-2 text-sm text-foreground shadow-sm"
        value={current || list[0]?.id}
        onChange={(e) => {
          const id = e.target.value;
          setWorkspaceId(id);
          setCurrent(id);
          window.location.reload();
        }}
      >
        {list.map((w) => (
          <option key={w.id} value={w.id}>
            {w.name} · {workspaceRoleLabel(w.role)}
          </option>
        ))}
      </select>
    </label>
  );
}
