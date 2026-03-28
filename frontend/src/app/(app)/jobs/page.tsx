"use client";

import { useCallback, useEffect, useState } from "react";
import { api, toErrorMessage, type IngestionJobOut } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";

const STATUSES = ["queued", "processing", "retrying", "ready", "failed"] as const;

export default function JobsPage() {
  const [tab, setTab] = useState<(typeof STATUSES)[number]>("failed");
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
        title="Очередь ingestion"
        description="Статусы задач: queued → processing / retrying → ready или failed."
      />
      <div className="flex flex-wrap gap-2">
        {STATUSES.map((s) => (
          <Button
            key={s}
            type="button"
            variant={tab === s ? "default" : "outline"}
            size="sm"
            className="font-mono text-xs"
            onClick={() => setTab(s)}
          >
            {s}
          </Button>
        ))}
      </div>
      {loading && <p className="text-sm text-muted-foreground">Загрузка…</p>}
      {err && <p className="text-sm text-destructive">{err}</p>}
      <div className="space-y-3">
        {!loading && jobs.length === 0 && !err && (
          <p className="text-sm text-muted-foreground">Нет задач со статусом «{tab}».</p>
        )}
        {jobs.map((j) => (
          <Card key={j.id}>
            <CardHeader>
              <CardTitle className="font-mono text-xs">{j.id}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1 text-sm">
              <div>document: {j.document_id}</div>
              <div>status: {j.status}</div>
              <div>attempts: {j.attempts}</div>
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
