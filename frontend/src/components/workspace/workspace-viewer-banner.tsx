"use client";

import { Eye } from "lucide-react";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { normalizeWorkspaceRole } from "@/lib/workspace-role";

/** Плашка только для роли viewer: единый визуальный контракт с API WorkspaceReadAccess. */
export function WorkspaceViewerBanner({ detail }: { detail: string }) {
  const { currentWorkspace } = useWorkspace();
  if (normalizeWorkspaceRole(currentWorkspace?.role) !== "viewer") return null;
  return (
    <div
      className="flex gap-2 rounded-xl border border-amber-500/45 bg-amber-500/10 px-3 py-2.5 text-sm text-amber-950 dark:text-amber-50"
      role="status"
    >
      <Eye className="mt-0.5 h-4 w-4 shrink-0 text-amber-700 dark:text-amber-200" aria-hidden />
      <div>
        <p className="font-medium text-amber-900 dark:text-amber-100">Роль «наблюдатель» (viewer)</p>
        <p className="mt-0.5 text-xs leading-relaxed text-amber-900/90 dark:text-amber-100/90">{detail}</p>
      </div>
    </div>
  );
}
