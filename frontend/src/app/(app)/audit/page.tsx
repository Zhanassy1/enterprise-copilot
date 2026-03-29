"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, toErrorMessage, type AuditLogOut, type WorkspaceOut } from "@/lib/api-client";
import { getWorkspaceId } from "@/lib/workspace";
import { workspaceRoleLabel } from "@/lib/product-terminology";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ProductErrorBanner } from "@/components/shared/product-error-banner";

type Tab = "standard" | "admin";

export default function AuditPage() {
  const [workspaces, setWorkspaces] = useState<WorkspaceOut[]>([]);
  const [tab, setTab] = useState<Tab>("standard");
  const [eventFilter, setEventFilter] = useState("");
  const [logs, setLogs] = useState<AuditLogOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const currentWs = useMemo(() => {
    const id = getWorkspaceId();
    return workspaces.find((w) => w.id === id) ?? workspaces[0];
  }, [workspaces]);

  const canAdminView = useMemo(() => {
    const r = (currentWs?.role ?? "").toLowerCase();
    return r === "owner" || r === "admin";
  }, [currentWs?.role]);

  const loadAudit = useCallback(
    async (filterText: string) => {
      setLoading(true);
      setErr(null);
      const q = filterText.trim() || undefined;
      try {
        if (tab === "admin" && canAdminView) {
          const rows = await api.listAuditLogsAdmin(200, q);
          setLogs(rows);
        } else {
          const rows = await api.listAuditLogs(100, q);
          setLogs(rows);
        }
      } catch (e) {
        setErr(toErrorMessage(e));
        setLogs([]);
      } finally {
        setLoading(false);
      }
    },
    [tab, canAdminView]
  );

  useEffect(() => {
    void api
      .listWorkspaces()
      .then(setWorkspaces)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (tab === "admin" && !canAdminView) {
      setTab("standard");
    }
  }, [tab, canAdminView]);

  useEffect(() => {
    if (tab === "admin" && !canAdminView) return;
    void loadAudit(eventFilter);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- фильтр не триггерит авто-запрос; только вкладка/роль
  }, [tab, canAdminView, loadAudit]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Журнал аудита"
        description="События безопасности и действий в текущем рабочем пространстве (входы, загрузки, отказы по квотам). Фильтр по типу события — точное совпадение; применяется кнопкой «Обновить»."
      />

      {currentWs && (
        <p className="text-sm text-muted-foreground">
          Роль в workspace: <span className="font-medium text-foreground">{workspaceRoleLabel(currentWs.role)}</span>
        </p>
      )}

      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="audit-event">Тип события (опционально)</Label>
          <Input
            id="audit-event"
            placeholder="например quota.denied"
            value={eventFilter}
            onChange={(e) => setEventFilter(e.target.value)}
            className="w-full max-w-sm font-mono text-sm"
          />
        </div>
        <Button type="button" variant="secondary" onClick={() => void loadAudit(eventFilter)}>
          Обновить
        </Button>
      </div>

      {canAdminView && (
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant={tab === "standard" ? "default" : "outline"} size="sm" onClick={() => setTab("standard")}>
            Общий журнал
          </Button>
          <Button type="button" variant={tab === "admin" ? "default" : "outline"} size="sm" onClick={() => setTab("admin")}>
            Расширенный (владелец / администратор)
          </Button>
        </div>
      )}

      {loading && (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-24 w-full rounded-xl" />
        </div>
      )}
      {err ? (
        <ProductErrorBanner message={err} onRetry={() => void loadAudit(eventFilter)} />
      ) : null}

      {!loading && !err && logs.length === 0 && (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Записей пока нет или нет совпадений по фильтру. События появляются при действиях пользователей и при отказах по
            квотам.
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        {!loading &&
          logs.map((row) => (
            <Card key={row.id}>
              <CardHeader className="pb-2">
                <CardTitle className="font-mono text-xs text-muted-foreground">{row.event_type}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1 text-sm">
                <div className="text-xs text-muted-foreground">{row.created_at}</div>
                {row.user_id && <div>user: {row.user_id}</div>}
                {(row.target_type || row.target_id) && (
                  <div>
                    target: {row.target_type ?? "—"} {row.target_id ? `· ${row.target_id}` : ""}
                  </div>
                )}
                {row.metadata_json && (
                  <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-2 text-xs">
                    {row.metadata_json}
                  </pre>
                )}
              </CardContent>
            </Card>
          ))}
      </div>
    </div>
  );
}
