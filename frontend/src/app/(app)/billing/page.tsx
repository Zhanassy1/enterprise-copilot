"use client";

import { useEffect, useState } from "react";
import { api, toErrorMessage, type UsageSummaryOut } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/page-header";

export default function BillingPage() {
  const [data, setData] = useState<UsageSummaryOut | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void api
      .getBillingUsage()
      .then(setData)
      .catch((e) => setErr(toErrorMessage(e)));
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader title="План и usage" description="Квоты workspace и расход за текущий месяц." />
      {err && <p className="text-sm text-destructive">{err}</p>}
      {data && (
        <Card>
          <CardHeader>
            <CardTitle>План: {data.plan_slug}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm sm:grid-cols-2">
            <div>Документов (сейчас / лимит)</div>
            <div>
              {data.document_count}
              {data.max_documents != null ? ` / ${data.max_documents}` : " / ∞"}
            </div>
            <div>Запросы (месяц)</div>
            <div>
              {data.usage_requests_month} / {data.monthly_request_limit}
            </div>
            <div>Токены LLM (месяц)</div>
            <div>
              {data.usage_tokens_month} / {data.monthly_token_limit}
            </div>
            <div>Загрузка байт (месяц)</div>
            <div>
              {data.usage_bytes_month} / {data.monthly_upload_bytes_limit}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
