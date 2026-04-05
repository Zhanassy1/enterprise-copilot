"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ListTodo } from "lucide-react";
import { toast } from "sonner";
import { api, toErrorMessage, type IngestionJobOut } from "@/lib/api-client";
import { pipelineStatusLabel, PRODUCT_SECTION } from "@/lib/product-terminology";
import { PIPELINE_JOB_STATUSES } from "@/lib/ingestion-statuses";
import { canUploadDocuments } from "@/lib/workspace-role";
import { workspaceAppHref } from "@/lib/workspace-path";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/page-header";
import { ProductEmptyState } from "@/components/shared/product-empty-state";
import { ProductErrorBanner } from "@/components/shared/product-error-banner";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { WorkspaceProductContext } from "@/components/workspace/workspace-product-context";

export default function JobsPage() {
  const { currentWorkspace } = useWorkspace();
  const canUpload = canUploadDocuments(currentWorkspace?.role);
  const [tab, setTab] = useState<(typeof PIPELINE_JOB_STATUSES)[number]>("queued");
  const [jobs, setJobs] = useState<IngestionJobOut[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback((status: (typeof PIPELINE_JOB_STATUSES)[number]) => {
    setLoading(true);
    setErr(null);
    void api
      .listIngestionJobs(status)
      .then(setJobs)
      .catch((e) => {
        const msg = toErrorMessage(e);
        setErr(msg);
        toast.error(msg);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load(tab);
  }, [tab, load]);

  return (
    <div className="space-y-6">
      <PageHeader
        title={PRODUCT_SECTION.ingestionQueue}
        description={`${PRODUCT_SECTION.ingestionJob} только для текущего ${PRODUCT_SECTION.workspace.toLowerCase()}: те же фазы, что и статус документа в каталоге.`}
      />
      <WorkspaceProductContext
        area="задачи индексации ниже относятся к этому рабочему пространству"
        viewerDetail="Очередь доступна для наблюдения. Перезапуск и администрирование задач, если появятся в API, будут скрыты или помечены до выдачи прав."
      />
      <Card className="border-dashed bg-muted/20">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Статусы задачи индексации</CardTitle>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground">
          <ul className="list-inside list-disc space-y-1">
            <li>
              <strong className="text-foreground">В очереди</strong> — ждёт обработки; <strong className="text-foreground">Индексация</strong> — идёт
              разбор файла (та же подпись, что у документа в каталоге); <strong className="text-foreground">Повторная попытка</strong> — временная ошибка, будет ещё попытка.
            </li>
            <li>
              <strong className="text-foreground">Готово</strong> — документ доступен для поиска и чата; <strong className="text-foreground">Ошибка</strong>{" "}
              — смотрите текст ошибки в карточке задачи.
            </li>
          </ul>
        </CardContent>
      </Card>
      <div className="flex flex-wrap gap-2">
        {PIPELINE_JOB_STATUSES.map((s) => (
          <Button
            key={s}
            type="button"
            variant={tab === s ? "default" : "outline"}
            size="sm"
            className="text-xs"
            onClick={() => setTab(s)}
          >
            {pipelineStatusLabel(s)}
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
          <ProductEmptyState
            icon={ListTodo}
            title="Нет задач в этом фильтре"
            description={
              <>
                Нет задач со статусом «{pipelineStatusLabel(tab)}». Переключите фильтр выше
                {canUpload && currentWorkspace?.slug
                  ? " или загрузите документ — появится новая задача индексации."
                  : " или попросите участника загрузить документ."}
              </>
            }
          >
            {canUpload && currentWorkspace?.slug ? (
              <Button type="button" variant="outline" size="sm" asChild>
                <Link href={workspaceAppHref(currentWorkspace.slug, "/documents")}>К документам</Link>
              </Button>
            ) : null}
          </ProductEmptyState>
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
                  Статус: {pipelineStatusLabel(j.status)}{" "}
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
