"use client";

import { Building2, RefreshCw } from "lucide-react";
import { workspaceRoleLabel } from "@/lib/product-terminology";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { cn } from "@/lib/utils";

export function WorkspaceSwitcher() {
  const {
    workspaces,
    currentWorkspace,
    loading,
    error,
    hadStaleSelection,
    refresh,
    selectWorkspace,
  } = useWorkspace();

  if (loading) {
    return (
      <div className="mb-2 px-1">
        <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          Рабочее пространство
        </p>
        <Skeleton className="h-[4.5rem] w-full rounded-xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mb-2 space-y-2 rounded-xl border border-destructive/40 bg-destructive/5 px-3 py-2.5">
        <p className="text-xs font-medium text-destructive">{error}</p>
        <Button type="button" variant="outline" size="sm" className="h-8 w-full" onClick={() => void refresh()}>
          <RefreshCw className="mr-2 h-3.5 w-3.5" aria-hidden />
          Повторить
        </Button>
      </div>
    );
  }

  if (workspaces.length === 0) {
    return (
      <div className="mb-2 rounded-xl border border-dashed border-muted-foreground/40 bg-muted/30 px-3 py-3 text-xs text-muted-foreground">
        <p className="font-medium text-foreground">Нет доступных workspace</p>
        <p className="mt-1">
          У аккаунта нет привязки к рабочему пространству. Обычно при регистрации создаётся личное пространство — если
          список пуст, обратитесь к оператору или поддержке.
        </p>
        <Button type="button" variant="ghost" size="sm" className="mt-2 h-8" onClick={() => void refresh()}>
          Обновить
        </Button>
      </div>
    );
  }

  const effectiveId = currentWorkspace?.id ?? workspaces[0]!.id;

  return (
    <div className="mb-2 px-1">
      <p className="mb-1.5 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        <Building2 className="h-3 w-3" aria-hidden />
        Текущий workspace
      </p>
      <div className="rounded-xl border border-border/80 bg-card p-3 shadow-sm">
        {currentWorkspace ? (
          <>
            <div className="flex items-start justify-between gap-2">
              <p className="min-w-0 flex-1 text-sm font-semibold leading-snug text-foreground">
                {currentWorkspace.name}
              </p>
              <Badge variant="secondary" className="shrink-0 tabular-nums">
                {workspaceRoleLabel(currentWorkspace.role)}
              </Badge>
            </div>
            <p className="mt-1 truncate font-mono text-[10px] leading-tight text-muted-foreground" title={currentWorkspace.id}>
              {currentWorkspace.id}
            </p>
            {hadStaleSelection ? (
              <p className="mt-2 rounded-md bg-amber-500/15 px-2 py-1 text-[11px] text-amber-900 dark:text-amber-100">
                Ранее выбранный workspace недоступен — выбран первый из списка. Проверьте контекст данных.
              </p>
            ) : null}
          </>
        ) : (
          <p className="text-xs text-destructive">
            Не удалось сопоставить выбранный id со списком. Переключите workspace ниже или обновите список.
          </p>
        )}

        <label className={cn("mt-3 block", !currentWorkspace && "opacity-90")}>
          <span className="sr-only">Переключить рабочее пространство</span>
          <select
            className="w-full rounded-lg border border-input bg-background px-2.5 py-2 text-sm text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value={effectiveId}
            onChange={(e) => selectWorkspace(e.target.value)}
          >
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name} ({workspaceRoleLabel(w.role)})
              </option>
            ))}
          </select>
        </label>

        <div className="mt-0 flex items-center justify-between gap-2 border-t border-border/60 pt-2">
          <span className="text-[10px] text-muted-foreground">{workspaces.length} в аккаунте</span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-[10px] text-muted-foreground"
            onClick={() => void refresh()}
          >
            Обновить список
          </Button>
        </div>
      </div>
    </div>
  );
}
