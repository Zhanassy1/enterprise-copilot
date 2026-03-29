"use client";

import Link from "next/link";
import { ArrowRight, BadgeCheck, Info } from "lucide-react";
import { marketingPlans, type MarketingPlan } from "@/config/plan-marketing";
import {
  isKnownMarketingPlan,
  nextPublicPlanSlug,
  normalizePlanSlug,
  planDisplayName,
} from "@/lib/plan-labels";
import { siteUrls } from "@/lib/site-urls";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function planAnchor(slug: string): string {
  return `/pricing#pricing-plan-${normalizePlanSlug(slug)}`;
}

function upgradeLabel(from: string): { href: string; label: string } | null {
  const n = nextPublicPlanSlug(from);
  if (!n) return null;
  return {
    href: planAnchor(n),
    label: n === "pro" ? "Следующий уровень: Pro" : "Следующий уровень: Team",
  };
}

interface InAppPlanComparisonProps {
  currentPlanSlug: string;
}

export function InAppPlanComparison({ currentPlanSlug }: InAppPlanComparisonProps) {
  const current = normalizePlanSlug(currentPlanSlug);
  const upgrade = upgradeLabel(current);

  return (
    <section id="plan-comparison" className="scroll-mt-8 space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Сравнение планов</h2>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Free, Pro и Team — эталонные лимиты продукта (как в{" "}
            <a
              href={siteUrls.githubQuotas}
              className="text-foreground underline underline-offset-2"
              target="_blank"
              rel="noreferrer"
            >
              docs/quotas.md
            </a>
            ). У вашего{" "}
            <span className="font-medium text-foreground">рабочего пространства (workspace)</span> фактические потолки
            приходят из API выше; при ручной настройке они могут отличаться от таблицы.
          </p>
        </div>
        {upgrade ? (
          <Button asChild>
            <Link href={upgrade.href} className="inline-flex items-center gap-2">
              {upgrade.label}
              <ArrowRight className="h-4 w-4" aria-hidden />
            </Link>
          </Button>
        ) : (
          <Button variant="outline" asChild>
            <Link href="/pricing">Публичная страница тарифов</Link>
          </Button>
        )}
      </div>

      <div className="flex gap-2 rounded-lg border border-dashed border-muted-foreground/35 bg-muted/30 p-3 text-sm text-muted-foreground">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-foreground/70" aria-hidden />
        <p>
          Оплата и автоматическое переключение плана в продукте пока не подключены: тариф в данных workspace задаёт
          администратор или процесс онбординга. Страница <Link href="/pricing" className="underline underline-offset-2">/pricing</Link> — для выбора уровня при регистрации и для сравнения возможностей.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {marketingPlans.map((p: MarketingPlan) => {
          const active = normalizePlanSlug(p.slug) === current;
          return (
            <Card
              key={p.slug}
              id={`app-plan-${p.slug}`}
              className={
                p.highlight && !active
                  ? "border-primary/40 shadow-sm lg:ring-1 lg:ring-primary/10"
                  : active
                    ? "border-primary shadow-md ring-2 ring-primary/20"
                    : "border-border/80"
              }
            >
              <CardHeader className="space-y-2 pb-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <CardTitle className="text-base">{p.name}</CardTitle>
                  {active ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-primary/15 px-2 py-0.5 text-xs font-medium text-primary">
                      <BadgeCheck className="h-3.5 w-3.5" aria-hidden />
                      текущий план API
                    </span>
                  ) : (
                    <span className="text-xs text-muted-foreground">{p.hint}</span>
                  )}
                </div>
                <p className="text-xs font-medium text-foreground">{p.audience}</p>
                <p className="text-xs text-muted-foreground">{p.positioning}</p>
              </CardHeader>
              <CardContent className="space-y-3 pt-0">
                <div>
                  <p className="text-xs font-medium text-foreground">Включено и ограничено</p>
                  <ul className="mt-2 space-y-1.5 text-xs text-muted-foreground">
                    {p.bullets.map((b) => (
                      <li key={b} className="flex gap-2">
                        <span className="text-primary" aria-hidden>
                          •
                        </span>
                        <span>{b}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <Button variant={active ? "secondary" : "outline"} className="w-full" size="sm" asChild>
                  <Link href={planAnchor(p.slug)} className="inline-flex items-center justify-center gap-1">
                    Подробнее на /pricing
                    <ArrowRight className="h-3.5 w-3.5 opacity-70" aria-hidden />
                  </Link>
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {!isKnownMarketingPlan(currentPlanSlug) ? (
        <p className="text-xs text-amber-800 dark:text-amber-200">
          План «{planDisplayName(currentPlanSlug)}» не совпадает с публичными Free / Pro / Team — сверяйте лимиты только с
          блоком «Использование за месяц» выше.
        </p>
      ) : null}
    </section>
  );
}
