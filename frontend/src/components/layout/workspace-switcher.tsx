"use client";

import { useEffect, useState } from "react";
import { api, type WorkspaceOut } from "@/lib/api-client";
import { getWorkspaceId, setWorkspaceId } from "@/lib/workspace";

export function WorkspaceSwitcher() {
  const [list, setList] = useState<WorkspaceOut[]>([]);
  const [current, setCurrent] = useState<string>("");

  useEffect(() => {
    setCurrent(getWorkspaceId() ?? "");
    void api
      .listWorkspaces()
      .then((w) => {
        setList(w);
        if (w.length && !getWorkspaceId()) {
          setWorkspaceId(w[0].id);
          setCurrent(w[0].id);
        }
      })
      .catch(() => {});
  }, []);

  if (list.length === 0) return null;

  return (
    <label className="mb-2 block px-3 text-xs text-muted-foreground">
      Workspace
      <select
        className="mt-1 w-full rounded-md border border-input bg-background px-2 py-2 text-sm text-foreground"
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
            {w.name} · {w.role}
          </option>
        ))}
      </select>
    </label>
  );
}
