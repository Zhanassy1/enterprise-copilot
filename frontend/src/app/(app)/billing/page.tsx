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
import { Skeleton } from "@/components/ui/skeleton";

export default function BillingPage() {
  const [data, setData] = useState<UsageSummaryOut | null>(null);
  const [ledger, setLedger] = useState<BillingLedgerOut[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    void Promise.all([api.getBillingUsage(), api.listBillingLedger()])
      .then(([u, l]) => {
        setData(u);
        setLedger(l);
      })
      .catch((e) => setErr(toErrorMessage(e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        title="План и лимиты"
        description="Тариф workspace и расход за текущий месяц (UTC). Лимиты согласованы с планом free / pro / team — см. документацию репозитория."
      />
      {err && <p className="text-sm text-destructive">{err}</p>}

      {loading && (
        <div className="space-y-4">
          <Skeleton className="h-48 w-full rounded-xl" />
          <Skeleton className="h-32 w-full rounded-xl" />
        </div>
      )}

      {!loading && data && (
        <Card>
          <CardHeader>
            <CardTitle>План: {data.plan_slug}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm sm:grid-cols-2">
            <div>Документов (сейчас / лимит)</div>
            <div>
              {data.document_count}
              {data.max_documents != null ? ` / ${data.max_documents}` : " / без лимита"}
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

      <Card className="border-dashed">
        <CardHeader>
          <CardTitle className="text-base">Оплата</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Подключение Stripe или другого провайдера — в roadmap. Сейчас план задаётся данными workspace и отражается в usage API;
          ledger ниже может быть пустым до интеграции биллинга.
        </CardContent>
      </Card>

      {ledger.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>История списаний (ledger)</CardTitle>
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

      {!loading && ledger.length === 0 && !err && (
        <p className="text-sm text-muted-foreground">Записей ledger пока нет — ожидаемо до подключения биллинга.</p>
      )}
    </div>
  );
}
