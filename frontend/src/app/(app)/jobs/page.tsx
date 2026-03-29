"use client";

import { useCallback, useEffect, useState } from "react";
import { api, toErrorMessage, type IngestionJobOut } from "@/lib/api-client";
import { ingestionJobStatusLabel } from "@/lib/product-terminology";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/page-header";
import { ProductErrorBanner } from "@/components/shared/product-error-banner";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { WorkspaceContextStrip } from "@/components/workspace/workspace-context-strip";

const STATUSES = ["queued", "processing", "retrying", "ready", "failed"] as const;

export default function JobsPage() {
  const [tab, setTab] = useState<(typeof STATUSES)[number]>("queued");
  const [jobs, setJobs] = useState<IngestionJobOut[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback((status: (typeof STATUSES)[number]) => {
    setLoading(true);
    setErr(null);
    void api
      .listIngestionJobs(status)
      .then(setJobs)
      .catch((e) => setErr(toErrorMessage(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load(tab);
  }, [tab, load]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Очередь обработки"
        description="Задачи индексации (jobs) только для текущего workspace: в очереди → индексация или повтор → готово либо ошибка. Статус на карточке документа ссылается на ту же очередь."
      />
      <div className="mt-1">
        <WorkspaceContextStrip area="задачи индексации ниже относятся к этому workspace" />
      </div>
      <Card className="border-dashed bg-muted/20">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Статусы задачи (job)</CardTitle>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground">
          <ul className="list-inside list-disc space-y-1">
            <li>
              <strong className="text-foreground">В очереди</strong> — ждёт обработки; <strong className="text-foreground">Индексация</strong> — идёт
              разбор файла; <strong className="text-foreground">Повторная попытка</strong> — временная ошибка, будет ещё попытка.
            </li>
            <li>
              <strong className="text-foreground">Готово</strong> — документ доступен для поиска и чата; <strong className="text-foreground">Ошибка</strong>{" "}
              — смотрите текст ошибки в карточке задачи.
            </li>
          </ul>
        </CardContent>
      </Card>
      <div className="flex flex-wrap gap-2">
        {STATUSES.map((s) => (
          <Button
            key={s}
            type="button"
            variant={tab === s ? "default" : "outline"}
            size="sm"
            className="text-xs"
            onClick={() => setTab(s)}
          >
            {ingestionJobStatusLabel(s)}
            <span className="ml-1 font-mono text-[10px] opacity-70">({s})</span>
          </Button>
        ))}
      </div>
      {loading && (
        <div className="space-y-3">
          <Skeleton className="h-28 w-full rounded-xl" />
          <Skeleton className="h-28 w-full rounded-xl" />
        </div>
      )}
      {err ? (
        <ProductErrorBanner message={err} onRetry={() => load(tab)} retryLabel="Повторить загрузку списка" />
      ) : null}
      <div className="space-y-3">
        {!loading && jobs.length === 0 && !err && (
          <p className="text-sm text-muted-foreground">
            Нет задач со статусом «{ingestionJobStatusLabel(tab)}». Загрузите документ или переключите фильтр.
          </p>
        )}
        {!loading &&
          jobs.map((j) => (
            <Card key={j.id}>
              <CardHeader>
                <CardTitle className="font-mono text-xs">{j.id}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1 text-sm">
                <div>Документ: {j.document_id}</div>
                <div>
                  Статус: {ingestionJobStatusLabel(j.status)}{" "}
                  <span className="font-mono text-xs text-muted-foreground">({j.status})</span>
                </div>
                <div>Попытки: {j.attempts}</div>
                {j.error_message && (
                  <pre className="whitespace-pre-wrap rounded bg-muted p-2 text-xs">{j.error_message}</pre>
                )}
              </CardContent>
            </Card>
          ))}
      </div>
    </div>
  );
}
