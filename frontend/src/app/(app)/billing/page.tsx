"use client";

import { useEffect, useState } from "react";
import {
  api,
  toErrorMessage,
  type BillingLedgerOut,
  type UsageSummaryOut,
} from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/page-header";

export default function BillingPage() {
  const [data, setData] = useState<UsageSummaryOut | null>(null);
  const [ledger, setLedger] = useState<BillingLedgerOut[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([api.getBillingUsage(), api.listBillingLedger()])
      .then(([u, l]) => {
        setData(u);
        setLedger(l);
      })
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
      {ledger.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Ledger (последние записи)</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="py-2 pr-2">Тип</th>
                  <th className="py-2 pr-2">Сумма</th>
                  <th className="py-2 pr-2">Валюта</th>
                  <th className="py-2">Время</th>
                </tr>
              </thead>
              <tbody>
                {ledger.map((row) => (
                  <tr key={row.id} className="border-b border-border/60">
                    <td className="py-2 pr-2 font-mono text-xs">{row.event_type}</td>
                    <td className="py-2 pr-2">{row.amount_cents}</td>
                    <td className="py-2 pr-2">{row.currency}</td>
                    <td className="py-2 text-xs text-muted-foreground">{row.created_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
