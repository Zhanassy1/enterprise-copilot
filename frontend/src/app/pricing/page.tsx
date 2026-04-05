import Link from "next/link";
import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MarketingShell } from "@/components/marketing/marketing-shell";
import { PricingPlanActions } from "@/components/marketing/pricing-plan-actions";
import { marketingPlans } from "@/config/plan-marketing";
import { siteUrls } from "@/lib/site-urls";

export default function PricingPage() {
  return (
    <MarketingShell>
      <main>
        <section className="border-b bg-gradient-to-b from-muted/40 to-background px-4 py-14 sm:px-6">
          <div className="mx-auto max-w-3xl text-center">
            <p className="text-sm font-medium text-muted-foreground">Тарифы</p>
            <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">Планы Free, Pro и Team</h1>
            <p className="mt-4 text-muted-foreground">
              Три ступени масштаба — одна кодовая база. После входа у каждого{" "}
              <span className="font-medium text-foreground">рабочего пространства (workspace)</span> на странице{" "}
              <span className="font-medium text-foreground">«План и лимиты»</span> (
              <code className="rounded bg-muted px-1 font-mono text-xs">/billing</code>) видны фактический тариф и остатки
              квот в реальном времени. Онлайн-оплата (Stripe) подключена к тем же экранам: лимиты workspace обновляются из подписки
              после подтверждения Checkout и вебхуков.
            </p>
            <div className="mx-auto mt-8 flex max-w-xl flex-col gap-2 sm:flex-row sm:justify-center">
              <Button variant="secondary" asChild>
                <a href={siteUrls.evaluatorGuide} target="_blank" rel="noreferrer">
                  Чек-лист оценки за 5 минут (README)
                </a>
              </Button>
              <Button variant="outline" asChild>
                <a href={siteUrls.demoScreenshots} target="_blank" rel="noreferrer">
                  Скриншоты UI в репозитории
                </a>
              </Button>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
          <div className="grid gap-6 lg:grid-cols-3">
            {marketingPlans.map((p) => (
              <Card
                key={p.slug}
                id={`pricing-plan-${p.slug}`}
                className={
                  p.highlight ? "border-primary shadow-lg ring-2 ring-primary/15 lg:scale-[1.02]" : "border-border/80"
                }
              >
                <CardHeader className="space-y-2">
                  <div className="flex items-baseline justify-between gap-2">
                    <CardTitle className="text-xl">{p.name}</CardTitle>
                    <span className="text-xs font-medium text-muted-foreground">{p.hint}</span>
                  </div>
                  <p className="text-sm font-medium text-foreground">{p.audience}</p>
                  <p className="text-sm text-muted-foreground">{p.positioning}</p>
                </CardHeader>
                <CardContent className="space-y-4">
                  <ul className="space-y-2 text-sm text-muted-foreground">
                    {p.bullets.map((b) => (
                      <li key={b} className="flex gap-2">
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
                        <span>{b}</span>
                      </li>
                    ))}
                  </ul>
                  <PricingPlanActions planSlug={p.slug} planName={p.name} highlight={p.highlight} />
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 pb-4 sm:px-6">
          <div className="grid gap-4 md:grid-cols-3">
            <Card className="border-border/80">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">Free — пилот</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                Проверка гипотезы на одном контуре: поиск и чат по своим файлам с понятным потолком запросов.
              </CardContent>
            </Card>
            <Card className="border-primary/30 ring-1 ring-primary/10">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">Pro — рабочий режим</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                Ежедневная работа команды: больше запросов, объём загрузок и параллельных индексаций без «упора» на каждом
                аплоаде.
              </CardContent>
            </Card>
            <Card className="border-border/80">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">Team — масштаб</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                Высокая частота запросов и крупные корпуса документов; максимум публичной шкалы перед индивидуальным
                enterprise-соглашением.
              </CardContent>
            </Card>
          </div>
        </section>

        <section id="pricing-comparison" className="scroll-mt-8 border-y bg-muted/25 px-4 py-12 sm:px-6">
          <div className="mx-auto max-w-4xl">
            <h2 className="text-xl font-semibold">Сравнение лимитов</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Цифры ниже — опорные для переговоров с администратором инстанса; источник истины по всем квотам —{" "}
              <a href={siteUrls.githubQuotas} className="font-medium text-foreground underline underline-offset-2" target="_blank" rel="noreferrer">
                docs/quotas.md
              </a>
              .
            </p>
            <div className="mt-6 overflow-x-auto rounded-xl border bg-card">
              <table className="w-full min-w-[32rem] text-left text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="p-3 font-medium">Критерий</th>
                    <th className="p-3 font-medium">Free</th>
                    <th className="p-3 font-medium">Pro</th>
                    <th className="p-3 font-medium">Team</th>
                  </tr>
                </thead>
                <tbody className="text-muted-foreground">
                  <tr className="border-b">
                    <td className="p-3 text-foreground">Запросы / мес</td>
                    <td className="p-3">2 000</td>
                    <td className="p-3">50 000</td>
                    <td className="p-3">500 000</td>
                  </tr>
                  <tr className="border-b">
                    <td className="p-3 text-foreground">Документов (потолок)</td>
                    <td className="p-3">50</td>
                    <td className="p-3">10 000</td>
                    <td className="p-3">без жёсткого лимита</td>
                  </tr>
                  <tr className="border-b">
                    <td className="p-3 text-foreground">Параллельные задачи индексации</td>
                    <td className="p-3">2</td>
                    <td className="p-3">8</td>
                    <td className="p-3">32</td>
                  </tr>
                  <tr>
                    <td className="p-3 text-foreground">PDF на документ</td>
                    <td className="p-3">до 150 стр.</td>
                    <td className="p-3">до 2 000 стр.</td>
                    <td className="p-3">без лимита</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="mt-4 text-xs text-muted-foreground">
              Полная таблица включая токены и объём загрузок — в{" "}
              <a href={siteUrls.githubQuotas} className="text-foreground underline underline-offset-2" target="_blank" rel="noreferrer">
                docs/quotas.md
              </a>
              .
            </p>
          </div>
        </section>

        <section className="mx-auto max-w-4xl px-4 py-12 text-center sm:px-6">
          <h2 className="text-lg font-semibold">Готовы попробовать?</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Регистрация бесплатна. После входа выберите рабочее пространство (workspace) и откройте{" "}
            <strong className="text-foreground">«План и лимиты»</strong> — там счётчики месяца, прогресс по квотам и ссылки на
            апгрейд.             Апгрейд через Stripe Checkout и управление картой в Customer Portal — на странице «План и лимиты»
            внутри приложения.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Button size="lg" asChild>
              <Link href="/register">Создать аккаунт · Free</Link>
            </Button>
            <Button size="lg" variant="secondary" asChild>
              <Link href="/login">Уже есть аккаунт · Войти</Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link href="/#demo-quick-1min">Демо за 1 минуту (главная)</Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <a href={siteUrls.demoMedia} target="_blank" rel="noreferrer">
                Сценарий демо в docs
              </a>
            </Button>
          </div>
        </section>
      </main>
    </MarketingShell>
  );
}
