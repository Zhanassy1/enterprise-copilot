import Link from "next/link";
import {
  Activity,
  ArrowRight,
  Building2,
  Gauge,
  Layers,
  Shield,
  Sparkles,
  Target,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MarketingShell } from "@/components/marketing/marketing-shell";
import { siteUrls } from "@/lib/site-urls";
import { marketingPlans } from "@/config/plan-marketing";

const productTagline =
  "Один продукт — от загрузки договора до ответа с указанием страницы, на которой это написано.";

const features = [
  {
    title: "Отдельное рабочее пространство",
    body: "Каждый workspace — свой каталог документов и своя база для поиска. Роли: владелец, администратор, участник, наблюдатель — с разными правами на действия.",
    icon: Building2,
  },
  {
    title: "Индексация без ожидания у экрана",
    body: "Загрузили файл — дальше он обрабатывается в фоне. В каталоге видны статус документа и ход задачи индексации; когда всё готово, доступны поиск и чат.",
    icon: Layers,
  },
  {
    title: "План и квоты",
    body: "Запросы (поиск, сообщения, загрузки), токены модели, объём загрузок и число одновременных индексаций ограничены тарифом Free, Pro или Team.",
    icon: Gauge,
  },
  {
    title: "Безопасность и аудит",
    body: "Вход по паролю, контроль сессий, события в журнале аудита workspace — чтобы отвечать на вопросы «кто и что делал».",
    icon: Shield,
  },
  {
    title: "Ответы с источниками",
    body: "Поиск и диалог опираются на ваши PDF, DOCX и текст: к ответу приложены выдержки из документов, а не общие фразы модели.",
    icon: Sparkles,
  },
  {
    title: "Готово к эксплуатации",
    body: "Для команды, которая разворачивает продукт у себя: контроль лимитов, логи, метрики и памятка для операторов описаны в документации.",
    icon: Activity,
  },
];

const valueProps = [
  {
    title: "Меньше рутинного чтения",
    body: "Сотрудники переходят к вопросам вида «какой срок?», «какая сумма?» — и получают ответ с опорой на конкретный файл.",
    icon: Zap,
  },
  {
    title: "Данные не смешиваются",
    body: "Команда A и команда B не видят чужие документы: всё привязано к выбранному workspace и правам роли.",
    icon: Target,
  },
  {
    title: "Понятный путь к запуску",
    body: "Веб-интерфейс для пользователей и прозрачные лимиты плана — не только «интеграция через API для разработчиков».",
    icon: Shield,
  },
];

const howSteps = [
  {
    step: "1",
    title: "Регистрация и вход",
    body: "Создайте аккаунт и откройте приложение. Выберите рабочее пространство в переключателе (если доступно несколько).",
  },
  {
    step: "2",
    title: "Загрузка документов",
    body: "Добавьте PDF, DOCX или текст. Пока идёт подготовка к поиску, статус виден на карточке и в разделе очереди обработки.",
  },
  {
    step: "3",
    title: "Поиск, чат и краткое содержание",
    body: "Задайте вопрос по смыслу или откройте краткое содержание файла — ответы строятся по уже проиндексированным материалам.",
  },
  {
    step: "4",
    title: "План, квоты и аудит",
    body: "Страница «План и лимиты» показывает расход месяца. Журнал аудита доступен для контроля событий (в т.ч. отказы по квотам).",
  },
];

export function LandingPage() {
  return (
    <MarketingShell>
      <main>
        <section className="relative overflow-hidden border-b bg-gradient-to-b from-muted/45 via-background to-background px-4 pb-20 pt-16 sm:px-6 sm:pt-20">
          <div
            className="pointer-events-none absolute inset-0 opacity-40"
            style={{
              background:
                "radial-gradient(ellipse 75% 55% at 50% -10%, color-mix(in oklch, var(--color-muted-foreground) 12%, transparent), transparent 55%)",
            }}
          />
          <div className="relative mx-auto max-w-3xl text-center">
            <p className="text-sm font-medium uppercase tracking-widest text-muted-foreground">Для команд с договорами и регламентами</p>
            <h1 className="mt-4 text-balance text-4xl font-bold tracking-tight sm:text-5xl lg:text-[3.25rem]">
              Находите ответы в своих документах — быстро и с указанием источника
            </h1>
            <p className="mx-auto mt-4 max-w-2xl text-lg font-medium text-foreground/90">{productTagline}</p>
            <p className="mx-auto mt-4 max-w-2xl text-muted-foreground">
              Загрузка файлов, фоновая подготовка к поиску, семантический поиск и диалог в рамках workspace. Роли участников,
              лимиты плана и журнал событий — как в зрелом B2B-продукте.
            </p>
            <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
              <Button size="lg" asChild>
                <Link href="/register">
                  Попробовать бесплатно
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link href="/pricing">Смотреть тарифы</Link>
              </Button>
              <Button size="lg" variant="ghost" asChild>
                <Link href="/login">Уже есть аккаунт</Link>
              </Button>
            </div>
            <p className="mx-auto mt-8 max-w-lg text-xs text-muted-foreground">
              Оплата банковской картой через провайдера в планах на будущее. Сейчас в интерфейсе отображаются план и использование
              без списаний.
            </p>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
          <h2 className="text-center text-2xl font-semibold">Зачем это бизнесу</h2>
          <p className="mx-auto mt-2 max-w-2xl text-center text-sm text-muted-foreground">
            Сфокусированный сценарий: меньше времени на поиск формулировок в длинных файлах — больше на решения.
          </p>
          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {valueProps.map((v) => (
              <Card key={v.title} className="border-border/80 shadow-sm">
                <CardHeader>
                  <v.icon className="h-8 w-8 text-primary" aria-hidden />
                  <CardTitle className="text-lg">{v.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">{v.body}</p>
                </CardContent>
              </Card>
            ))}
          </div>
          <div className="mt-10 flex flex-wrap justify-center gap-3">
            <Button size="lg" variant="secondary" asChild>
              <Link href="/register">Начать с Free</Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <a href={siteUrls.evaluatorGuide} target="_blank" rel="noreferrer">
                Оценить за 5 минут
              </a>
            </Button>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
          <h2 className="text-center text-2xl font-semibold">Возможности</h2>
          <p className="mx-auto mt-2 max-w-2xl text-center text-sm text-muted-foreground">
            Всё, что нужно команде для ежедневной работы с корпоративными файлами в одном workspace.
          </p>
          <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((f) => (
              <Card key={f.title} className="border-border/80 shadow-sm">
                <CardHeader>
                  <f.icon className="h-8 w-8 text-primary" aria-hidden />
                  <CardTitle className="text-lg">{f.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">{f.body}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        <section className="border-y bg-muted/30 px-4 py-14 sm:px-6">
          <div className="mx-auto max-w-5xl">
            <h2 className="text-center text-2xl font-semibold">Как это работает</h2>
            <p className="mx-auto mt-2 max-w-2xl text-center text-sm text-muted-foreground">
              Четыре шага от первого входа до контроля лимитов — без схем «только для инженеров».
            </p>
            <ol className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {howSteps.map((s) => (
                <li key={s.step}>
                  <Card className="h-full border-border/80 bg-card shadow-sm">
                    <CardHeader className="pb-2">
                      <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                        {s.step}
                      </span>
                      <CardTitle className="pt-2 text-base">{s.title}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground">{s.body}</p>
                    </CardContent>
                  </Card>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
          <h2 className="text-center text-2xl font-semibold">Тарифы</h2>
          <p className="mx-auto mt-2 max-w-2xl text-center text-sm text-muted-foreground">
            Подробное описание и таблица сравнения — на отдельной странице. Ниже — краткий обзор; полные цифры совпадают с
            документацией продукта.
          </p>
          <div className="mt-8 flex justify-center">
            <Button variant="outline" asChild>
              <Link href="/pricing">Открыть страницу тарифов</Link>
            </Button>
          </div>
          <div className="mt-10 grid gap-6 lg:grid-cols-3">
            {marketingPlans.map((p) => (
              <Card
                key={p.slug}
                className={
                  p.highlight ? "border-primary shadow-md ring-2 ring-primary/15" : "border-border/80 shadow-sm"
                }
              >
                <CardHeader>
                  <CardTitle className="flex items-baseline justify-between gap-2 text-lg">
                    <span>{p.name}</span>
                    <span className="text-xs font-normal text-muted-foreground">{p.hint}</span>
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">{p.audience}</p>
                </CardHeader>
                <CardContent className="space-y-3">
                  <ul className="space-y-1.5 text-sm text-muted-foreground">
                    {p.bullets.slice(0, 4).map((row) => (
                      <li key={row}>• {row}</li>
                    ))}
                    <li className="text-xs">… и ещё лимиты — на странице тарифов</li>
                  </ul>
                  <Button className="w-full" variant={p.highlight ? "default" : "outline"} asChild>
                    <Link href="/register">Начать с {p.name}</Link>
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        <section className="border-t bg-muted/20 px-4 py-12 sm:px-6">
          <div className="mx-auto max-w-3xl text-center">
            <h2 className="text-xl font-semibold">Видео-демо</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Встроенный плеер появляется, если задан <code className="rounded bg-muted px-1">NEXT_PUBLIC_DEMO_VIDEO_EMBED_URL</code>{" "}
              (URL для iframe: YouTube embed, Vimeo и т.д.). Пока без URL — заготовка; сценарий записи — в{" "}
              <a href={siteUrls.demoMedia} className="text-foreground underline" target="_blank" rel="noreferrer">
                docs/DEMO_MEDIA.md
              </a>
              .
            </p>
            {process.env.NEXT_PUBLIC_DEMO_VIDEO_EMBED_URL ? (
              <div className="mx-auto mt-6 aspect-video w-full max-w-3xl overflow-hidden rounded-xl border bg-black shadow-sm">
                <iframe
                  src={process.env.NEXT_PUBLIC_DEMO_VIDEO_EMBED_URL}
                  title="Enterprise Copilot — демо"
                  className="h-full w-full"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                  allowFullScreen
                />
              </div>
            ) : (
              <div className="mt-6 flex aspect-video max-h-64 items-center justify-center rounded-xl border-2 border-dashed border-muted-foreground/30 bg-muted/40 text-sm text-muted-foreground">
                Слот под demo video — см.{" "}
                <a href={siteUrls.demoMedia} className="ml-1 text-foreground underline" target="_blank" rel="noreferrer">
                  docs/DEMO_MEDIA.md
                </a>
                {" "}
                и README (секция «Демо-видео»).
              </div>
            )}
          </div>
        </section>

        <section className="mx-auto max-w-4xl px-4 py-12 sm:px-6">
          <div className="flex flex-col items-center gap-4 rounded-2xl border bg-card px-6 py-10 text-center shadow-sm sm:flex-row sm:justify-between sm:text-left">
            <div>
              <h2 className="text-xl font-semibold">Подключите первый документ</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Регистрация занимает минуту. Дальше — загрузка, очередь обработки и поиск по содержимому.
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2 sm:justify-end">
              <Button size="lg" asChild>
                <Link href="/register">Создать аккаунт</Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <a href={siteUrls.evaluatorGuide} target="_blank" rel="noreferrer">
                  Чек-лист 5 минут
                </a>
              </Button>
            </div>
          </div>
        </section>
      </main>
    </MarketingShell>
  );
}
