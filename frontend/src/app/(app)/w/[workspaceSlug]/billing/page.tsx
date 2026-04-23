"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import {
  ApiError,
  api,
  toErrorMessage,
  type BillingInvoiceOut,
  type BillingLedgerOut,
  type BillingState,
  type SubscriptionOut,
  type UsageSummaryOut,
} from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/page-header";
import { ProductErrorBanner } from "@/components/shared/product-error-banner";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ExternalLink, AlertTriangle } from "lucide-react";
import { QuotaUsageRow } from "@/components/billing/quota-usage-row";
import { InAppPlanComparison } from "@/components/billing/in-app-plan-comparison";
import {
  nextPublicPlanSlug,
  planDisplayName,
  normalizePlanSlug,
  prevPublicPlanSlug,
} from "@/lib/plan-labels";
import { siteUrls } from "@/lib/site-urls";
import { WorkspaceProductContext } from "@/components/workspace/workspace-product-context";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { canManageBillingCheckout } from "@/lib/workspace-role";
import { PRODUCT_SECTION } from "@/lib/product-terminology";
import { billingCheckoutReturnUrls, workspaceAppHref } from "@/lib/workspace-path";
import { resolvedWorkspaceSlug } from "@/lib/workspace";

function monthPeriodLabelUtc(): string {
  const d = new Date();
  const month = d.toLocaleString("ru-RU", { month: "long", timeZone: "UTC" });
  return `${month} ${d.getUTCFullYear()} (UTC)`;
}

function formatUtcDateLabel(iso: string | null | undefined): string | null {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString("ru-RU", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "UTC",
    });
  } catch {
    return null;
  }
}

function formatMoneyMinorUnits(cents: number, currency: string): string {
  const cur = (currency || "usd").toUpperCase();
  try {
    return new Intl.NumberFormat("ru-RU", { style: "currency", currency: cur }).format(cents / 100);
  } catch {
    return `${(cents / 100).toFixed(2)} ${cur}`;
  }
}

function subscriptionStatusPresentation(
  sub: SubscriptionOut,
): {
  label: string;
  variant: "default" | "secondary" | "destructive" | "outline";
} {
  const ui = (sub.billing_state ?? "free") as BillingState;
  const labels: Record<BillingState, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
    active: { label: "Активен", variant: "default" },
    trialing: { label: "Пробный период", variant: "secondary" },
    grace: { label: "Льготный период (grace)", variant: "secondary" },
    past_due: { label: "Просрочен (past due)", variant: "destructive" },
    canceled: { label: "Отменена", variant: "destructive" },
    free: { label: "Без платной подписки", variant: "outline" },
  };
  return labels[ui] ?? { label: (sub.subscription_status || "").trim() || "—", variant: "outline" };
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
  const params = useParams();
  const routeWorkspaceSlug = typeof params.workspaceSlug === "string" ? params.workspaceSlug : "";
  const { currentWorkspace } = useWorkspace();
  const wsSlug = routeWorkspaceSlug || resolvedWorkspaceSlug(currentWorkspace);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const cancelToastShown = useRef(false);
  const canBilling = canManageBillingCheckout(currentWorkspace?.role ?? "");
  const [data, setData] = useState<UsageSummaryOut | null>(null);
  const [ledger, setLedger] = useState<BillingLedgerOut[]>([]);
  const [sub, setSub] = useState<SubscriptionOut | null>(null);
  const [invoices, setInvoices] = useState<BillingInvoiceOut[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [billingAct, setBillingAct] = useState(false);

  const openPortal = async () => {
    if (!canBilling) return;
    setBillingAct(true);
    try {
      const base =
        typeof window !== "undefined"
          ? `${window.location.origin}${window.location.pathname}`
          : "http://localhost:3000/billing";
      const { url } = await api.createBillingPortal(base);
      window.location.assign(url);
    } catch (e) {
      toast.error(toErrorMessage(e));
    } finally {
      setBillingAct(false);
    }
  };

  const openCheckout = async (planSlug: "pro" | "team") => {
    if (!canBilling || !wsSlug) return;
    setBillingAct(true);
    try {
      const origin = typeof window !== "undefined" ? window.location.origin : "";
      const { successUrl, cancelUrl } = billingCheckoutReturnUrls(origin, wsSlug);
      const { url } = await api.createBillingCheckout(successUrl, cancelUrl, planSlug);
      window.location.assign(url);
    } catch (e) {
      toast.error(toErrorMessage(e));
    } finally {
      setBillingAct(false);
    }
  };

  const reload = useCallback(() => {
    setLoading(true);
    setErr(null);
    void (async () => {
      try {
        const s = await api.getBillingSubscription();
        setSub(s);
      } catch (e) {
        const msg = toErrorMessage(e);
        setErr(msg);
        toast.error(msg);
        setSub(null);
      }
      if (!canBilling) {
        setData(null);
        setLedger([]);
        setInvoices([]);
        setLoading(false);
        return;
      }
      try {
        const [u, l] = await Promise.all([api.getBillingUsage(), api.listBillingLedger()]);
        setData(u);
        setLedger(l);
        const inv = await api.getBillingInvoices().catch((e) => {
          if (e instanceof ApiError && e.status === 503) return [];
          throw e;
        });
        setInvoices(inv);
      } catch (e) {
        const msg = toErrorMessage(e);
        setErr(msg);
        toast.error(msg);
      } finally {
        setLoading(false);
      }
    })();
  }, [canBilling]);

  useEffect(() => {
    reload();
  }, [reload, currentWorkspace?.id]);

  useEffect(() => {
    if (searchParams.get("checkout") !== "cancel") {
      cancelToastShown.current = false;
      return;
    }
    if (cancelToastShown.current) return;
    cancelToastShown.current = true;
    toast.message("Оформление отменено");
    router.replace(pathname, { scroll: false });
  }, [searchParams, router, pathname]);

  const alerts = useMemo(() => (data ? usageAlerts(data) : []), [data]);

  const planSlugForCta = data?.plan_slug ?? sub?.plan_slug ?? "free";
  const upgrade = nextPublicPlanSlug(planSlugForCta);
  /** Следующий публичный тариф; на Team без следующего — остаёмся на team Checkout (продление/смена). */
  const stripeCheckoutPlan = (upgrade ?? "team") as "pro" | "team";
  const downgradeTarget = prevPublicPlanSlug(planSlugForCta);
  const planHref =
    upgrade === "pro"
      ? "/pricing#pricing-plan-pro"
      : upgrade === "team"
        ? "/pricing#pricing-plan-team"
        : "/pricing";

  const statusUi = sub ? subscriptionStatusPresentation(sub) : null;

  return (
    <div className="space-y-8">
      <PageHeader
        title={PRODUCT_SECTION.planAndQuotas}
        description={`${PRODUCT_SECTION.workspace}: план и расход квот за календарный месяц — ${monthPeriodLabelUtc()}. Запросы — поиск, сообщения в чате и загрузки документов (считаются в одном месячном счётчике).`}
      />

      <WorkspaceProductContext
        className="mt-1"
        area="план, лимиты и счётчики usage относятся к этому рабочему пространству"
        viewerDetail="Просмотр плана и квот доступен; оформление подписки и клиентский портал оплаты — только у владельца и администратора."
        memberLimit={!canBilling ? "checkout" : null}
      />

      {!loading && sub && statusUi ? (
        <Card id="billing-payment-section" className="border-primary/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Настройки оплаты (Billing)</CardTitle>
            <p className="text-sm text-muted-foreground">
              Статус подписки и счета. Смена карты, снижение тарифа (downgrade) и отмена подписки выполняются в{" "}
              <span className="font-medium text-foreground">клиентском портале Stripe</span> (включите нужные действия в
              Stripe Dashboard → Billing → Customer portal). Сроки смены плана — по правилам Stripe (часто до конца
              оплаченного периода).
            </p>
            {downgradeTarget && canBilling ? (
              <p className="text-sm text-muted-foreground">
                Понизить уровень с {planDisplayName(planSlugForCta)} до {planDisplayName(downgradeTarget)} можно в портале;
                апгрейд на Pro или Team — кнопкой «Оформить подписку» или блоком сравнения планов ниже.
              </p>
            ) : null}
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted-foreground">Статус:</span>
              <Badge variant={statusUi.variant}>{statusUi.label}</Badge>
              <span className="text-sm text-muted-foreground">
                План:{" "}
                <span className="font-medium text-foreground">{planDisplayName(sub.plan_slug)}</span>{" "}
                <span className="font-mono text-xs">({normalizePlanSlug(sub.plan_slug)})</span>
              </span>
            </div>
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              {formatUtcDateLabel(sub.trial_ends_at) ? (
                <div>
                  <dt className="text-muted-foreground">Окончание пробного периода (UTC)</dt>
                  <dd className="font-medium">{formatUtcDateLabel(sub.trial_ends_at)}</dd>
                </div>
              ) : null}
              {formatUtcDateLabel(sub.renewal_at ?? sub.current_period_end) ? (
                <div>
                  <dt className="text-muted-foreground">Продление / конец периода (UTC)</dt>
                  <dd className="font-medium">
                    {formatUtcDateLabel(sub.renewal_at ?? sub.current_period_end)}
                  </dd>
                </div>
              ) : null}
              {formatUtcDateLabel(sub.grace_until ?? sub.grace_ends_at) &&
              (sub.billing_state === "grace" || (sub.subscription_status || "").toLowerCase() === "past_due") ? (
                <div>
                  <dt className="text-muted-foreground">Льготный период (grace) до (UTC)</dt>
                  <dd className="font-medium">{formatUtcDateLabel(sub.grace_until ?? sub.grace_ends_at)}</dd>
                </div>
              ) : null}
            </dl>
            {canBilling ? (
              <div className="flex flex-wrap gap-2 border-t border-border/60 pt-4">
                <Button
                  type="button"
                  variant="default"
                  size="sm"
                  disabled={billingAct}
                  onClick={() => void openPortal()}
                >
                  Обновить карту
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={billingAct}
                  onClick={() => void openPortal()}
                >
                  Отменить подписку
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={billingAct}
                  onClick={() => void openCheckout(stripeCheckoutPlan)}
                >
                  Оформить подписку ({planDisplayName(stripeCheckoutPlan)})
                </Button>
              </div>
            ) : (
              <fieldset disabled className="space-y-2 border-t border-border/60 pt-4 opacity-75">
                <legend className="sr-only">Действия оплаты недоступны для вашей роли</legend>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" variant="default" size="sm" disabled title="Только владелец и администратор">
                    Обновить карту
                  </Button>
                  <Button type="button" variant="outline" size="sm" disabled title="Только владелец и администратор">
                    Отменить подписку
                  </Button>
                  <Button type="button" variant="secondary" size="sm" disabled title="Только владелец и администратор">
                    Оформить подписку
                  </Button>
                </div>
                <p className="text-sm text-muted-foreground">
                  Управление картой и подпиской доступно владельцу и администраторам {PRODUCT_SECTION.workspace.toLowerCase()}.
                </p>
              </fieldset>
            )}
            {canBilling ? (
              <div className="space-y-2 border-t border-border/60 pt-4">
                <h3 className="text-sm font-medium">Счета (Invoices)</h3>
                {invoices.length > 0 ? (
                  <div className="overflow-x-auto rounded-lg border border-border/60">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="border-b bg-muted/40 text-muted-foreground">
                          <th className="px-3 py-2">№</th>
                          <th className="px-3 py-2">Дата</th>
                          <th className="px-3 py-2">Статус</th>
                          <th className="px-3 py-2">Сумма</th>
                          <th className="px-3 py-2">Документы</th>
                        </tr>
                      </thead>
                      <tbody>
                        {invoices.map((inv) => (
                          <tr key={inv.id} className="border-b border-border/50">
                            <td className="px-3 py-2 font-mono text-xs">{inv.number ?? inv.id.slice(0, 12)}</td>
                            <td className="px-3 py-2 text-muted-foreground">
                              {formatUtcDateLabel(inv.created) ?? "—"}
                            </td>
                            <td className="px-3 py-2">{inv.status ?? "—"}</td>
                            <td className="px-3 py-2">{formatMoneyMinorUnits(inv.amount_paid || inv.amount_due, inv.currency)}</td>
                            <td className="px-3 py-2">
                              <div className="flex flex-wrap gap-2">
                                {inv.invoice_pdf ? (
                                  <a
                                    href={inv.invoice_pdf}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="text-primary underline underline-offset-2"
                                  >
                                    PDF
                                  </a>
                                ) : null}
                                {inv.hosted_invoice_url ? (
                                  <a
                                    href={inv.hosted_invoice_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="text-primary underline underline-offset-2"
                                  >
                                    Счёт
                                  </a>
                                ) : null}
                                {!inv.invoice_pdf && !inv.hosted_invoice_url ? (
                                  <span className="text-muted-foreground">—</span>
                                ) : null}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Счетов пока нет или Stripe не подключён к этому развёртыванию.
                  </p>
                )}
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Card className="border-primary/30 bg-gradient-to-br from-primary/8 via-background to-background">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Нужен больший план?</CardTitle>
          <p className="text-sm text-muted-foreground">
            Free подходит для пилота, Pro — для ежедневной работы команды, Team — для высокой нагрузки и крупных корпусов
            документов. Сравните лимиты и выберите следующую ступень; при необходимости согласуйте смену плана с
            администратором развёртывания.
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

      {!loading && canBilling && data ? (
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
                  <Button type="button" size="sm" disabled={billingAct} onClick={() => void openCheckout(upgrade)}>
                    Оформить {planDisplayName(upgrade)} (Stripe)
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
                  <>
                    <Button type="button" disabled={billingAct} onClick={() => void openCheckout(upgrade)}>
                      Оформить {planDisplayName(upgrade)} (Stripe)
                    </Button>
                    <Button variant="outline" asChild>
                      <Link href={planHref} className="inline-flex items-center gap-2">
                        Карточка на сайте
                        <ExternalLink className="h-4 w-4 opacity-80" aria-hidden />
                      </Link>
                    </Button>
                  </>
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
                upgradeHref="#billing-payment-section"
              />
              <QuotaUsageRow
                title="Токены (квота)"
                description="Сумма оценок: embedding (запрос в эмбеддер) + generation (текст ответа/уточнения) + устаревший счётчик llm_tokens, если есть. Всё списывается в один месячный лимит."
                used={data.usage_tokens_month}
                limit={data.monthly_token_limit}
                unit="tokens"
                upgradeHref="#billing-payment-section"
              />
              <ul className="ml-4 list-disc space-y-1 text-xs text-muted-foreground">
                <li>
                  Embedding:{" "}
                  <span className="font-mono text-foreground">{data.usage_embedding_tokens_month.toLocaleString()}</span>{" "}
                  tokens
                </li>
                <li>
                  Generation:{" "}
                  <span className="font-mono text-foreground">{data.usage_generation_tokens_month.toLocaleString()}</span>{" "}
                  tokens
                </li>
                {data.usage_llm_tokens_month > 0 ? (
                  <li>
                    Legacy <span className="font-mono">llm_tokens</span>:{" "}
                    <span className="font-mono text-foreground">{data.usage_llm_tokens_month.toLocaleString()}</span>
                  </li>
                ) : null}
              </ul>
              <QuotaUsageRow
                title="Объём загрузок"
                description="Суммарный размер принятых файлов за месяц после дедупликации (квота storage / upload bytes)."
                used={data.usage_bytes_month}
                limit={data.monthly_upload_bytes_limit}
                unit="bytes"
                upgradeHref="#billing-payment-section"
              />
              <QuotaUsageRow
                title="Документы в workspace"
                description="Количество неудалённых документов относительно потолка плана (если задан)."
                used={data.document_count}
                limit={data.max_documents}
                unit="documents"
                upgradeHref="#billing-payment-section"
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

          <InAppPlanComparison
            currentPlanSlug={data.plan_slug}
            canCheckout={canBilling}
            checkoutBusy={billingAct}
            onCheckoutPlan={(plan) => void openCheckout(plan)}
          />

          <Card className="border-dashed">
            <CardHeader>
              <CardTitle className="text-base">Оплата и учёт</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">План и лимиты</span> этого workspace хранятся в базе и
              обновляются из Stripe (Checkout, Customer Portal, вебхуки). Счётчики usage — фактические; ledger ниже
              отражает события биллинга.
            </CardContent>
          </Card>

          <Card className="border-dashed bg-muted/15">
            <CardHeader>
              <CardTitle className="text-base">Команда и приглашения</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <p>
                Участники, приглашения (отправка, повтор, отзыв) и смена ролей доступны через API и UI на странице{" "}
                {wsSlug ? (
                  <Link href={workspaceAppHref(wsSlug, "/team")} className="font-medium text-foreground underline underline-offset-2">
                    Команда
                  </Link>
                ) : (
                  <span className="font-medium text-foreground">Команда</span>
                )}
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
                Записей ledger пока нет — появятся после событий Stripe (оплата, обновление подписки и т.д.).
              </p>
            )
          )}
        </>
      ) : null}

      {!loading && canBilling && !data && !err ? (
        <p className="text-sm text-muted-foreground">Нет данных usage — попробуйте обновить страницу.</p>
      ) : null}
    </div>
  );
}
