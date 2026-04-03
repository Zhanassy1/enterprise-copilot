"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import {
  api,
  toErrorMessage,
  type BillingLedgerOut,
  type UsageSummaryOut,
} from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/page-header";
import { ProductErrorBanner } from "@/components/shared/product-error-banner";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { ExternalLink, AlertTriangle } from "lucide-react";
import { QuotaUsageRow } from "@/components/billing/quota-usage-row";
import { InAppPlanComparison } from "@/components/billing/in-app-plan-comparison";
import { nextPublicPlanSlug, planDisplayName, normalizePlanSlug } from "@/lib/plan-labels";
import { siteUrls } from "@/lib/site-urls";
import { WorkspaceContextStrip } from "@/components/workspace/workspace-context-strip";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { isOwnerOrAdmin } from "@/lib/workspace-role";

function monthPeriodLabelUtc(): string {
  const d = new Date();
  const month = d.toLocaleString("ru-RU", { month: "long", timeZone: "UTC" });
  return `${month} ${d.getUTCFullYear()} (UTC)`;
}

function usageAlerts(data: UsageSummaryOut): string[] {
  const msgs: string[] = [];
  if (data.usage_requests_month > data.monthly_request_limit) {
    msgs.push(
      "Месячная квота запросов превышена. Новые поиски, сообщения в чате и загрузки могут получать ответ 429 до следующего месяца (UTC) или повышения лимита."
    );
  }
  if (data.usage_tokens_month > data.monthly_token_limit) {
    msgs.push(
      "Месячная квота токенов LLM превышена. Генерация ответов может блокироваться до сброса периода или смены плана."
    );
  }
  if (data.usage_bytes_month > data.monthly_upload_bytes_limit) {
    msgs.push("Месячный объём загрузок превышен. Новые загрузки могут отклоняться до сброса квоты.");
  }
  if (data.max_documents != null && data.document_count > data.max_documents) {
    msgs.push(
      "Число документов в workspace выше потолка плана (возможно после смены лимита). Новые загрузки могут блокироваться до освобождения места."
    );
  }
  return msgs;
}

export default function BillingPage() {
  const { currentWorkspace } = useWorkspace();
  const canBilling = isOwnerOrAdmin(currentWorkspace?.role ?? "");
  const [data, setData] = useState<UsageSummaryOut | null>(null);
  const [ledger, setLedger] = useState<BillingLedgerOut[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [billingAct, setBillingAct] = useState(false);

  const openPortal = async () => {
    if (!canBilling) return;
    setBillingAct(true);
    try {
      const base =
        typeof window !== "undefined" ? `${window.location.origin}/billing` : "http://localhost:3000/billing";
      const { url } = await api.createBillingPortal(base);
      window.location.assign(url);
    } catch (e) {
      toast.error(toErrorMessage(e));
    } finally {
      setBillingAct(false);
    }
  };

  const openCheckout = async () => {
    if (!canBilling) return;
    setBillingAct(true);
    try {
      const { url } = await api.createBillingCheckout();
      window.location.assign(url);
    } catch (e) {
      toast.error(toErrorMessage(e));
    } finally {
      setBillingAct(false);
    }
  };

  const reload = () => {
    setLoading(true);
    void Promise.all([api.getBillingUsage(), api.listBillingLedger()])
      .then(([u, l]) => {
        setData(u);
        setLedger(l);
        setErr(null);
      })
      .catch((e) => {
        const msg = toErrorMessage(e);
        setErr(msg);
        toast.error(msg);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    reload();
  }, []);

  const alerts = useMemo(() => (data ? usageAlerts(data) : []), [data]);

  const upgrade = data ? nextPublicPlanSlug(data.plan_slug) : null;
  const planHref =
    upgrade === "pro"
      ? "/pricing#pricing-plan-pro"
      : upgrade === "team"
        ? "/pricing#pricing-plan-team"
        : "/pricing";

  return (
    <div className="space-y-8">
      <PageHeader
        title="План и лимиты"
        description={`Рабочее пространство (workspace): план и расход квот за календарный месяц — ${monthPeriodLabelUtc()}. Запросы — поиск, сообщения в чате и загрузки документов (считаются в одном месячном счётчике).`}
      />

      <WorkspaceContextStrip area="план, лимиты и счётчики usage относятся к этому workspace" />

      {canBilling ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Онлайн-оплата (Stripe)</CardTitle>
            <p className="text-sm text-muted-foreground">
              Портал Stripe — смена карты, счета и тарифа. Checkout — оформить подписку, если включён в развёртывании.
            </p>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button type="button" variant="default" size="sm" disabled={billingAct} onClick={() => void openCheckout()}>
              Оформить подписку
            </Button>
            <Button type="button" variant="outline" size="sm" disabled={billingAct} onClick={() => void openPortal()}>
              Клиентский портал биллинга
            </Button>
          </CardContent>
        </Card>
      ) : null}

      <Card className="border-primary/30 bg-gradient-to-br from-primary/8 via-background to-background">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Нужен больший план?</CardTitle>
          <p className="text-sm text-muted-foreground">
            Free подходит для пилота, Pro — для ежедневной работы команды, Team — для высокой нагрузки и крупных корпусов
            документов. Сравните лимиты и выберите следующую ступень — дальше согласуйте смену данных workspace с
            администратором развёртывания (онлайн-оплата в продукте запланирована отдельно).
          </p>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <div className="flex flex-wrap gap-2">
            <Button size="sm" asChild>
              <Link href="/pricing#pricing-comparison" className="inline-flex items-center gap-1.5">
                Сравнить все планы
                <ExternalLink className="h-3.5 w-3.5 opacity-70" aria-hidden />
              </Link>
            </Button>
            <Button size="sm" variant="secondary" asChild>
              <Link href="/pricing#pricing-plan-pro" className="inline-flex items-center gap-1.5">
                Фокус на Pro
                <ExternalLink className="h-3.5 w-3.5 opacity-70" aria-hidden />
              </Link>
            </Button>
            <Button size="sm" variant="outline" asChild>
              <Link href="/pricing#pricing-plan-team" className="inline-flex items-center gap-1.5">
                Фокус на Team
                <ExternalLink className="h-3.5 w-3.5 opacity-70" aria-hidden />
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" asChild>
          <Link href="/pricing#pricing-comparison" className="inline-flex items-center gap-1.5">
            Тарифы на сайте
            <ExternalLink className="h-3.5 w-3.5 opacity-70" aria-hidden />
          </Link>
        </Button>
        <Button variant="ghost" size="sm" asChild>
          <a href={siteUrls.githubQuotas} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5">
            docs/quotas.md
            <ExternalLink className="h-3.5 w-3.5 opacity-70" aria-hidden />
          </a>
        </Button>
      </div>

      {err ? (
        <ProductErrorBanner message={err} onRetry={() => reload()} retryLabel="Повторить запрос" />
      ) : null}

      {loading && (
        <div className="space-y-4">
          <Skeleton className="h-40 w-full rounded-xl" />
          <Skeleton className="h-56 w-full rounded-xl" />
        </div>
      )}

      {!loading && data ? (
        <>
          {alerts.length > 0 ? (
            <div
              className="space-y-3 rounded-xl border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive"
              role="alert"
            >
              <div className="flex gap-3">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
                <ul className="list-inside list-disc space-y-1">
                  {alerts.map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              </div>
              <div className="flex flex-wrap gap-2 border-t border-destructive/25 pt-3">
                <Button size="sm" variant="outline" asChild>
                  <Link href="/pricing#pricing-comparison">Сравнить планы и лимиты</Link>
                </Button>
                {upgrade ? (
                  <Button size="sm" asChild>
                    <Link href={planHref}>Рекомендуемый апгрейд: {planDisplayName(upgrade)}</Link>
                  </Button>
                ) : null}
              </div>
            </div>
          ) : null}

          <Card>
            <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <CardTitle className="text-xl">Текущий план workspace</CardTitle>
                <p className="mt-1 text-sm text-muted-foreground">
                  Активный тариф: <span className="font-semibold text-foreground">{planDisplayName(data.plan_slug)}</span>{" "}
                  (<span className="font-mono text-xs">{normalizePlanSlug(data.plan_slug)}</span>). Счётчики и потолки ниже
                  — из того же ответа API, без догадок.
                </p>
                {upgrade ? (
                  <p className="mt-2 text-sm font-medium text-primary">
                    Рекомендация: при росте нагрузки посмотрите {planDisplayName(upgrade)} — шире лимиты на тех же функциях.
                  </p>
                ) : (
                  <p className="mt-2 text-sm text-muted-foreground">
                    Уже на верхнем публичном уровне (Team) — дальнейший рост обсуждается с командой продукта под вашу нагрузку.
                  </p>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                {upgrade ? (
                  <Button asChild>
                    <Link href={planHref} className="inline-flex items-center gap-2">
                      Перейти на {planDisplayName(upgrade)}
                      <ExternalLink className="h-4 w-4 opacity-80" aria-hidden />
                    </Link>
                  </Button>
                ) : (
                  <Button variant="secondary" asChild>
                    <Link href="/pricing">Обзор всех планов</Link>
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <h3 className="text-sm font-medium">Использование за месяц</h3>
              <QuotaUsageRow
                title="Запросы"
                description="Поиск, сообщение в чате и загрузка документа — каждое событие увеличивает этот счётчик (квота requests)."
                used={data.usage_requests_month}
                limit={data.monthly_request_limit}
                unit="requests"
              />
              <QuotaUsageRow
                title="Токены LLM"
                description="Оценка входящих и исходящих токенов модели для поиска и чата (квота tokens)."
                used={data.usage_tokens_month}
                limit={data.monthly_token_limit}
                unit="tokens"
              />
              <QuotaUsageRow
                title="Объём загрузок"
                description="Суммарный размер принятых файлов за месяц после дедупликации (квота storage / upload bytes)."
                used={data.usage_bytes_month}
                limit={data.monthly_upload_bytes_limit}
                unit="bytes"
              />
              <QuotaUsageRow
                title="Документы в workspace"
                description="Количество неудалённых документов относительно потолка плана (если задан)."
                used={data.document_count}
                limit={data.max_documents}
                unit="documents"
              />
            </CardContent>
          </Card>

          <Card className="border-dashed border-muted-foreground/40 bg-muted/20">
            <CardHeader>
              <CardTitle className="text-base">Что не показывает этот экран</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>
                <span className="font-medium text-foreground">Проходы rerank</span>,{" "}
                <span className="font-medium text-foreground">параллельные задачи индексации (jobs)</span> и{" "}
                <span className="font-medium text-foreground">лимит страниц PDF на документ</span> задаются планом и
                проверяются API, но <strong>отдельные счётчики в GET /billing/usage не возвращаются</strong> — без
                догадок и заглушек-цифр.
              </p>
              <p>
                Сверяйте эти лимиты с карточками ниже и с{" "}
                <a href={siteUrls.githubQuotas} className="text-foreground underline underline-offset-2" target="_blank" rel="noreferrer">
                  docs/quotas.md
                </a>
                . Очередь задач — в разделе «Очередь обработки».
              </p>
            </CardContent>
          </Card>

          <InAppPlanComparison currentPlanSlug={data.plan_slug} />

          <Card className="border-dashed">
            <CardHeader>
              <CardTitle className="text-base">Оплата и учёт</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Сейчас <span className="font-medium text-foreground">план и квоты</span> задаются конфигурацией вашего
              развёртывания — UI показывает лимиты и расход прозрачно. Подключение Stripe, счетов или enterprise-договора
              привяжет те же экраны к живому биллингу; таблица ledger заполнится, когда начнёт поступать провайдер.
            </CardContent>
          </Card>

          <Card className="border-dashed bg-muted/15">
            <CardHeader>
              <CardTitle className="text-base">Команда и приглашения</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <p>
                Управление участниками, приглашения и смена ролей в API этой версии не даны как полноценный CRUD.
                Продуктовый контекст и честный статус — на странице{" "}
                <Link href="/team" className="font-medium text-foreground underline underline-offset-2">
                  Команда
                </Link>
                .
              </p>
            </CardContent>
          </Card>

          {ledger.length > 0 ? (
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
          ) : (
            !err && (
              <p className="text-sm text-muted-foreground">
                Записей ledger пока нет — ожидаемо до подключения внешнего биллинга.
              </p>
            )
          )}
        </>
      ) : null}

      {!loading && !data && !err ? (
        <p className="text-sm text-muted-foreground">Нет данных usage — попробуйте обновить страницу.</p>
      ) : null}
    </div>
  );
}
