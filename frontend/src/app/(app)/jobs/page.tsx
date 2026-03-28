"use client";

import { useEffect, useState } from "react";
import { api, toErrorMessage, type IngestionJobOut } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/page-header";

export default function JobsPage() {
  const [failed, setFailed] = useState<IngestionJobOut[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void api
      .listIngestionJobs("failed")
      .then(setFailed)
      .catch((e) => setErr(toErrorMessage(e)));
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Очередь ingestion"
        description="Задачи со статусом failed (dead-letter / ретраи исчерпаны)."
      />
      {err && <p className="text-sm text-destructive">{err}</p>}
      <div className="space-y-3">
        {failed.length === 0 && !err && (
          <p className="text-sm text-muted-foreground">Нет failed jobs.</p>
        )}
        {failed.map((j) => (
          <Card key={j.id}>
            <CardHeader>
              <CardTitle className="text-base font-mono text-xs">{j.id}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1 text-sm">
              <div>document: {j.document_id}</div>
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
