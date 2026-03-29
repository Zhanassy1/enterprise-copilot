"use client";

import { useWorkspace } from "@/components/workspace/workspace-provider";
import { Badge } from "@/components/ui/badge";
import { workspaceRoleLabel } from "@/lib/product-terminology";
import { Skeleton } from "@/components/ui/skeleton";

/** Короткая плашка: данные страницы относятся к выбранному workspace. */
export function WorkspaceContextStrip({ area }: { area: string }) {
  const { currentWorkspace, loading } = useWorkspace();

  if (loading) {
    return <Skeleton className="h-9 w-full max-w-xl rounded-lg" />;
  }
  if (!currentWorkspace) {
    return null;
  }

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border/70 bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
      <span className="min-w-0">
        Контекст:{" "}
        <span className="font-medium text-foreground">{currentWorkspace.name}</span>
        {" — "}
        {area}
      </span>
      <Badge variant="outline" className="shrink-0 font-normal">
        {workspaceRoleLabel(currentWorkspace.role)}
      </Badge>
    </div>
  );
}
