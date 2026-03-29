"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, toErrorMessage, ApiError, type AuditLogOut } from "@/lib/api-client";
import { workspaceRoleLabel } from "@/lib/product-terminology";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import {
  AUDIT_SERVER_FILTER_PRESETS,
  getAuditEventPresentation,
  targetTypeHint,
} from "@/lib/audit-event-labels";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ProductErrorBanner } from "@/components/shared/product-error-banner";
import {
  ClipboardList,
  Filter,
  Info,
  Lock,
  ShieldAlert,
  Inbox,
  SearchX,
} from "lucide-react";

type Tab = "standard" | "admin";

function formatIsoLocal(iso: string): string {
  try {
    return new Date(iso).toLocaleString("ru-RU", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

function formatMetadata(raw: string | null | undefined): string {
  if (!raw?.trim()) return "";
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

export default function AuditPage() {
  const { currentWorkspace: currentWs } = useWorkspace();
  const [tab, setTab] = useState<Tab>("standard");
  const [serverEventType, setServerEventType] = useState("");
  const [customServerEvent, setCustomServerEvent] = useState("");
  const [actorFilter, setActorFilter] = useState("");
  const [targetTypeFilter, setTargetTypeFilter] = useState("");
  const [targetIdFilter, setTargetIdFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [rawLogs, setRawLogs] = useState<AuditLogOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<{ message: string; status: number } | null>(null);
  const [lastFetchMode, setLastFetchMode] = useState<"none" | "ok" | "error">("none");

  const serverFilterRef = useRef({ serverEventType, customServerEvent });
  serverFilterRef.current = { serverEventType, customServerEvent };

  const canAdminView = useMemo(() => {
    const r = (currentWs?.role ?? "").toLowerCase();
    return r === "owner" || r === "admin";
  }, [currentWs?.role]);

  const fetchLimit = useMemo(() => {
    if (tab === "admin" && canAdminView) return 500;
    if (canAdminView) return 200;
    return 50;
  }, [tab, canAdminView]);

  const loadAudit = useCallback(async () => {
    setLoading(true);
    setErr(null);
    const { serverEventType: st, customServerEvent: ce } = serverFilterRef.current;
    const eff = st === "__custom__" ? ce.trim() : st.trim();
    const q = eff || undefined;
    try {
      if (tab === "admin" && canAdminView) {
        const rows = await api.listAuditLogsAdmin(fetchLimit, q);
        setRawLogs(rows);
      } else {
        const rows = await api.listAuditLogs(fetchLimit, q);
        setRawLogs(rows);
      }
      setLastFetchMode("ok");
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      setErr({ message: toErrorMessage(e), status });
      setRawLogs([]);
      setLastFetchMode("error");
    } finally {
      setLoading(false);
    }
  }, [tab, canAdminView, fetchLimit]);

  useEffect(() => {
    if (tab === "admin" && !canAdminView) {
      setTab("standard");
    }
  }, [tab, canAdminView]);

  useEffect(() => {
    if (tab === "admin" && !canAdminView) return;
    void loadAudit();
  }, [tab, canAdminView, loadAudit]);

  const displayedLogs = useMemo(() => {
    const af = actorFilter.trim().toLowerCase();
    const tf = targetTypeFilter.trim().toLowerCase();
    const tid = targetIdFilter.trim().toLowerCase();
    const fromTs = dateFrom ? new Date(dateFrom).getTime() : null;
    const toTs = dateTo ? new Date(dateTo).getTime() : null;

    return rawLogs.filter((row) => {
      if (af && !(row.user_id ?? "").toLowerCase().includes(af)) return false;
      if (tf && !(row.target_type ?? "").toLowerCase().includes(tf)) return false;
      if (tid && !(row.target_id ?? "").toLowerCase().includes(tid)) return false;
      const t = new Date(row.created_at).getTime();
      if (fromTs !== null && !Number.isNaN(fromTs) && t < fromTs) return false;
      if (toTs !== null && !Number.isNaN(toTs) && t > toTs) return false;
      return true;
    });
  }, [rawLogs, actorFilter, targetTypeFilter, targetIdFilter, dateFrom, dateTo]);

  const clientFiltered =
    !!actorFilter.trim() ||
    !!targetTypeFilter.trim() ||
    !!targetIdFilter.trim() ||
    !!dateFrom ||
    !!dateTo;

  const clearClientFilters = () => {
    setActorFilter("");
    setTargetTypeFilter("");
    setTargetIdFilter("");
    setDateFrom("");
    setDateTo("");
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Журнал аудита"
        description="События безопасности и действий в текущем рабочем пространстве (workspace). Данные приходят из API с ограничениями ниже — без догадок о несуществующих фильтрах."
      />

      {currentWs ? (
        <Card className="border-border/80 bg-muted/20">
          <CardContent className="flex flex-wrap items-start gap-3 py-4 text-sm">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
            <div className="min-w-0 flex-1 space-y-1">
              <p>
                <span className="font-medium text-foreground">Workspace:</span>{" "}
                <span className="text-foreground">{currentWs.name}</span>
                <span className="ml-2 font-mono text-xs text-muted-foreground">{currentWs.id}</span>
              </p>
              <p className="text-muted-foreground">
                Ваша роль:{" "}
                <span className="font-medium text-foreground">{workspaceRoleLabel(currentWs.role)}</span>
                {canAdminView ? (
                  <> — доступен расширенный журнал (до 500 записей за запрос).</>
                ) : (
                  <> — расширенный режим только у владельца и администратора; обычный запрос до 50 записей.</>
                )}
              </p>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card className="border-dashed border-amber-500/40 bg-amber-500/5">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base font-medium">
            <Info className="h-4 w-4 shrink-0" aria-hidden />
            Возможности API (честный degraded UI)
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <ul className="list-inside list-disc space-y-1">
            <li>
              <strong className="text-foreground">Сервер</strong> фильтрует только по{" "}
              <code className="rounded bg-muted px-1">event_type</code> (точное совпадение) и режет выдачу по лимиту.
            </li>
            <li>
              <strong className="text-foreground">Участник, объект, диапазон дат</strong> — фильтры только в браузере,
              среди уже загруженных строк (последние N событий).
            </li>
            <li>Журнал всегда для заголовка <code className="rounded bg-muted px-1">X-Workspace-Id</code> — другой workspace из UI не запрашивается.</li>
          </ul>
        </CardContent>
      </Card>

      <div className="space-y-4 rounded-2xl border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-2 text-sm font-medium text-foreground">
          <Filter className="h-4 w-4 text-muted-foreground" aria-hidden />
          Фильтры
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <div className="space-y-1.5 md:col-span-2">
            <Label htmlFor="audit-server-event">Тип события (сервер, точное имя)</Label>
            <select
              id="audit-server-event"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={serverEventType}
              onChange={(e) => setServerEventType(e.target.value)}
            >
              {AUDIT_SERVER_FILTER_PRESETS.map((o) => (
                <option key={o.value || "__all__"} value={o.value}>
                  {o.label}
                </option>
              ))}
              <option value="__custom__">Другой тип (вручную)…</option>
            </select>
            {serverEventType === "__custom__" ? (
              <Input
                className="mt-2 font-mono text-sm"
                placeholder="например quota.denied"
                value={customServerEvent}
                onChange={(e) => setCustomServerEvent(e.target.value)}
                aria-label="Произвольный тип события для API"
              />
            ) : null}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="audit-actor">Участник (actor / user_id)</Label>
            <Input
              id="audit-actor"
              placeholder="фрагмент UUID"
              value={actorFilter}
              onChange={(e) => setActorFilter(e.target.value)}
              className="font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">Только среди загруженных записей.</p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="audit-target-type">Тип объекта (target_type)</Label>
            <Input
              id="audit-target-type"
              placeholder="workspace, document…"
              value={targetTypeFilter}
              onChange={(e) => setTargetTypeFilter(e.target.value)}
              className="text-sm"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="audit-target-id">Идентификатор объекта (target_id)</Label>
            <Input
              id="audit-target-id"
              placeholder="фрагмент id"
              value={targetIdFilter}
              onChange={(e) => setTargetIdFilter(e.target.value)}
              className="font-mono text-sm"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="audit-from">Время от (локально)</Label>
            <Input
              id="audit-from"
              type="datetime-local"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="audit-to">Время до (локально)</Label>
            <Input
              id="audit-to"
              type="datetime-local"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 border-t pt-4">
          <Button type="button" variant="default" onClick={() => void loadAudit()} disabled={loading}>
            Загрузить с сервера
          </Button>
          <Button type="button" variant="outline" onClick={clearClientFilters} disabled={!clientFiltered}>
            Сбросить локальные фильтры
          </Button>
          <span className="text-xs text-muted-foreground">
            Лимит выдачи: <strong className="text-foreground">{fetchLimit}</strong> записей за запрос
            {tab === "admin" ? " (расширенный режим)" : ""}.
          </span>
        </div>
      </div>

      {canAdminView ? (
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant={tab === "standard" ? "default" : "outline"} size="sm" onClick={() => setTab("standard")}>
            Общий журнал
          </Button>
          <Button type="button" variant={tab === "admin" ? "default" : "outline"} size="sm" onClick={() => setTab("admin")}>
            Расширенный (owner / admin)
          </Button>
        </div>
      ) : (
        <Card className="border-dashed">
          <CardContent className="flex gap-3 py-4 text-sm text-muted-foreground">
            <Lock className="mt-0.5 h-4 w-4 shrink-0 text-foreground/70" aria-hidden />
            <p>
              Режим <span className="font-medium text-foreground">«Расширенный»</span> и эндпоинт{" "}
              <code className="rounded bg-muted px-1">GET /audit/admin/logs</code> доступны только ролям{" "}
              <span className="font-medium text-foreground">владелец</span> и{" "}
              <span className="font-medium text-foreground">администратор</span>. У участника и наблюдателя API вернёт{" "}
              <span className="font-medium text-foreground">403</span> при попытке вызвать админ-маршрут — интерфейс не
              показывает этот таб.
            </p>
          </CardContent>
        </Card>
      )}

      {loading && (
        <div className="space-y-3">
          <Skeleton className="h-28 w-full rounded-xl" />
          <Skeleton className="h-28 w-full rounded-xl" />
          <Skeleton className="h-28 w-full rounded-xl" />
        </div>
      )}

      {err ? (
        err.status === 403 ? (
          <Card className="border-destructive/50 bg-destructive/10">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base text-destructive">
                <Lock className="h-4 w-4" aria-hidden />
                Доступ запрещён (403)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-destructive/90">
              <p>{err.message}</p>
              <p className="text-muted-foreground">
                Если вы недавно меняли роль, перезайдите или проверьте, что выбран верный workspace. Расширенный журнал
                смотрите под учётной записью владельца или администратора.
              </p>
              <Button type="button" variant="outline" size="sm" onClick={() => void loadAudit()}>
                Повторить
              </Button>
            </CardContent>
          </Card>
        ) : (
          <ProductErrorBanner message={err.message} onRetry={() => void loadAudit()} retryLabel="Повторить" />
        )
      ) : null}

      {!loading && !err && lastFetchMode === "ok" && rawLogs.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
            <Inbox className="h-10 w-10 text-muted-foreground" aria-hidden />
            <div className="space-y-1">
              <p className="font-medium text-foreground">Записей нет</p>
              <p className="max-w-md text-sm text-muted-foreground">
                По текущему workspace и серверному фильтру событий не найдено. События появятся после действий пользователей,
                отказов по квотам, ошибок индексации и т.д.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {!loading && !err && rawLogs.length > 0 && displayedLogs.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
            <SearchX className="h-10 w-10 text-muted-foreground" aria-hidden />
            <div className="space-y-1">
              <p className="font-medium text-foreground">Нет результатов по локальным фильтрам</p>
              <p className="max-w-md text-sm text-muted-foreground">
                Загружено <strong>{rawLogs.length}</strong> записей, но ни одна не проходит фильтры участника / объекта /
                времени. Ослабьте условия или нажмите «Сбросить локальные фильтры».
              </p>
            </div>
            <Button type="button" variant="secondary" size="sm" onClick={clearClientFilters}>
              Сбросить локальные фильтры
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        {!loading &&
          !err &&
          displayedLogs.map((row) => {
            const pres = getAuditEventPresentation(row.event_type);
            const targetHint = targetTypeHint(row.target_type);
            return (
              <Card key={row.id}>
                <CardHeader className="pb-2">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <CardTitle className="text-base font-semibold leading-snug text-foreground">{pres.title}</CardTitle>
                      <p className="mt-1 font-mono text-xs text-muted-foreground">{row.event_type}</p>
                      {pres.hint ? <p className="mt-2 text-sm text-muted-foreground">{pres.hint}</p> : null}
                    </div>
                    <time className="shrink-0 text-xs tabular-nums text-muted-foreground" dateTime={row.created_at}>
                      {formatIsoLocal(row.created_at)}
                    </time>
                  </div>
                </CardHeader>
                <CardContent className="space-y-2 border-t border-border/50 pt-3 text-sm">
                  {row.user_id ? (
                    <div>
                      <span className="text-muted-foreground">Участник (user_id): </span>
                      <span className="font-mono text-xs">{row.user_id}</span>
                    </div>
                  ) : (
                    <div className="text-muted-foreground">Участник не указан (системное или фоновое событие)</div>
                  )}
                  {row.target_type || row.target_id ? (
                    <div>
                      <span className="text-muted-foreground">Объект: </span>
                      {row.target_type ?? "—"}
                      {row.target_id ? (
                        <span className="ml-1 font-mono text-xs">· {row.target_id}</span>
                      ) : null}
                      {targetHint ? <p className="mt-0.5 text-xs text-muted-foreground">{targetHint}</p> : null}
                    </div>
                  ) : null}
                  {row.metadata_json ? (
                    <details className="rounded-md border bg-muted/40">
                      <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-foreground">
                        Metadata (JSON)
                      </summary>
                      <pre className="max-h-48 overflow-auto whitespace-pre-wrap border-t px-3 py-2 text-xs">
                        {formatMetadata(row.metadata_json)}
                      </pre>
                    </details>
                  ) : null}
                </CardContent>
              </Card>
            );
          })}
      </div>

      {!loading && !err && displayedLogs.length > 0 ? (
        <p className="flex items-center gap-2 text-xs text-muted-foreground">
          <ClipboardList className="h-3.5 w-3.5 shrink-0" aria-hidden />
          Показано {displayedLogs.length} из {rawLogs.length} загруженных записей.
          {clientFiltered ? " Локальные фильтры активны." : null}
        </p>
      ) : null}
    </div>
  );
}
