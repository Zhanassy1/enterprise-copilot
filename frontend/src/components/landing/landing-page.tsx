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
import { siteUrls } from "@/lib/site-urls";
import { marketingPlans } from "@/config/plan-marketing";

const features = [
  {
    title: "Изоляция по workspace",
    body: "Каждое рабочее пространство — свой каталог документов и свой векторный индекс. Доступ: владелец, администратор, участник, наблюдатель.",
    icon: Building2,
  },
  {
    title: "Фоновая индексация",
    body: "После загрузки файл ставится в очередь: парсинг, фрагменты и векторы считает worker. В интерфейсе видны статус документа и задача индексации.",
    icon: Layers,
  },
  {
    title: "План и квоты",
    body: "Лимиты по запросам (поиск, чат, загрузка), токенам LLM, объёму загрузок и числу параллельных задач индексации согласованы с тарифом Free / Pro / Team.",
    icon: Gauge,
  },
  {
    title: "Безопасность и аудит",
    body: "JWT, обновление токенов, сброс пароля, записи в журнале аудита рабочего пространства — для соответствия корпоративным политикам.",
    icon: Shield,
  },
  {
    title: "Поиск и чат с источниками",
    body: "Семантический ответ по содержимому PDF, DOCX и текста с указанием фрагментов-источников, а не «голого» генеративного текста.",
    icon: Sparkles,
  },
  {
    title: "Наблюдаемость",
    body: "Корреляция запросов, метрики, runbook для операторов — чтобы жить в production, а не только в демо.",
    icon: Activity,
  },
];

const valueProps = [
  {
    title: "Меньше ручного чтения",
    body: "Сотрудники переходят от листания PDF к целевым вопросам и выдержкам с опорой на документы.",
    icon: Zap,
  },
  {
    title: "Данные в границах пространства",
    body: "Поиск и RAG не смешивают корпус разных команд: всё в рамках выбранного workspace и роли.",
    icon: Target,
  },
  {
    title: "Путь в production",
    body: "Асинхронная обработка, квоты, аудит и документация по деплою — не только прототип API.",
    icon: Shield,
  },
];

export function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b bg-card/80 backdrop-blur supports-[backdrop-filter]:bg-card/60">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link href="/" className="text-lg font-semibold tracking-tight">
            Enterprise Copilot
          </Link>
          <nav className="flex items-center gap-2 sm:gap-3">
            <a
              href={siteUrls.evaluatorGuide}
              className="hidden text-sm text-muted-foreground hover:text-foreground sm:inline"
              target="_blank"
              rel="noreferrer"
            >
              Оценка за 5 минут
            </a>
            <a
              href={siteUrls.githubDocs}
              className="hidden text-sm text-muted-foreground hover:text-foreground md:inline"
              target="_blank"
              rel="noreferrer"
            >
              Документация
            </a>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/login">Войти</Link>
            </Button>
            <Button size="sm" asChild>
              <Link href="/register">Регистрация</Link>
            </Button>
          </nav>
        </div>
      </header>

      <section className="relative overflow-hidden border-b bg-gradient-to-b from-muted/50 via-background to-background px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-sm font-medium uppercase tracking-widest text-muted-foreground">
            SaaS-платформа для AI над документами
          </p>
          <h1 className="mt-4 text-4xl font-bold tracking-tight sm:text-5xl">
            Корпоративные PDF и DOCX: поиск, ответы и чат — в изолированном рабочем пространстве
          </h1>
          <p className="mt-6 text-lg text-muted-foreground">
            Один контур для команд: загрузка в хранилище, фоновая индексация, семантический поиск и диалог с цитатами из ваших
            файлов. Лимиты плана, журнал аудита и готовность к промышленному развёртыванию.
          </p>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            <Button size="lg" asChild>
              <Link href="/register">
                Начать бесплатно
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link href="/login">Войти</Link>
            </Button>
          </div>
          <p className="mt-6 text-xs text-muted-foreground">
            Оплата через внешнего провайдера (например Stripe) в планах продукта. Сейчас отображаются план и расход без
            привязки к live-биллингу.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
        <h2 className="text-center text-2xl font-semibold">Ценность для бизнеса</h2>
        <p className="mx-auto mt-2 max-w-2xl text-center text-sm text-muted-foreground">
          Не абстрактный «AI», а рабочий сценарий: быстрее находить условия, даты и суммы в своих документах.
        </p>
        <div className="mt-10 grid gap-6 md:grid-cols-3">
          {valueProps.map((v) => (
            <Card key={v.title} className="border-border/80">
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
        <div className="mt-10 flex justify-center">
          <Button size="lg" variant="secondary" asChild>
            <Link href="/register">Подключить рабочее пространство</Link>
          </Button>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
        <h2 className="text-center text-2xl font-semibold">Возможности платформы</h2>
        <p className="mx-auto mt-2 max-w-2xl text-center text-sm text-muted-foreground">
          Регистрация → выбор workspace → загрузка → задача индексации → поиск, чат, краткое содержание → план и аудит.
        </p>
        <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <Card key={f.title} className="border-border/80">
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
        <div className="mx-auto max-w-6xl">
          <h2 className="text-2xl font-semibold">Как это устроено</h2>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
            Клиент передаёт идентификатор рабочего пространства (<code className="rounded bg-muted px-1">X-Workspace-Id</code>
            ). После принятия файла создаётся задача индексации в очереди; тяжёлая работа выполняется отдельным worker.
            Векторы хранятся в PostgreSQL (pgvector), файлы — локально или в S3.
          </p>
          <ul className="mt-6 list-inside list-disc space-y-2 text-sm text-muted-foreground">
            <li>Лимиты HTTP и месячные квоты зависят от плана рабочего пространства.</li>
            <li>Отказы по квотам попадают в журнал аудита и логи для эксплуатации.</li>
          </ul>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
        <h2 className="text-center text-2xl font-semibold">Тарифы</h2>
        <p className="mx-auto mt-2 max-w-2xl text-center text-sm text-muted-foreground">
          Цифры совпадают с таблицей в docs/quotas.md. Уточнение для своего workspace — в приложении на странице «План и
          лимиты».
        </p>
        <div className="mt-10 grid gap-6 lg:grid-cols-3">
          {marketingPlans.map((p) => (
            <Card
              key={p.slug}
              className={
                p.highlight ? "border-primary shadow-md ring-1 ring-primary/20" : "border-border/80"
              }
            >
              <CardHeader>
                <CardTitle className="flex items-baseline justify-between gap-2">
                  <span>{p.name}</span>
                  <span className="text-xs font-normal text-muted-foreground">{p.hint}</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  {p.bullets.map((row) => (
                    <li key={row}>• {row}</li>
                  ))}
                </ul>
                <Button className="mt-6 w-full" variant={p.highlight ? "default" : "outline"} asChild>
                  <Link href="/register">Начать с {p.name}</Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="border-t bg-muted/20 px-4 py-12 sm:px-6">
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-4 text-center sm:flex-row sm:justify-between sm:text-left">
          <div>
            <h2 className="text-xl font-semibold">Загрузите первый документ</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Регистрация и вход — затем документы, очередь индексации и поиск по содержимому.
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-2 sm:justify-end">
            <Button size="lg" asChild>
              <Link href="/register">Создать аккаунт</Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <a href={siteUrls.evaluatorGuide} target="_blank" rel="noreferrer">
                Гайд на 5 минут
              </a>
            </Button>
          </div>
        </div>
      </section>

      <footer className="border-t bg-card px-4 py-10 sm:px-6">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="font-semibold">Enterprise Copilot</p>
            <p className="mt-1 text-xs text-muted-foreground">
              SaaS-фундамент для AI над документами: workspace, квоты, аудит, UI и API.
            </p>
          </div>
          <div className="flex flex-col gap-2 text-sm sm:items-end">
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              <a href={siteUrls.githubGlossary} className="text-muted-foreground hover:text-foreground" target="_blank" rel="noreferrer">
                Глоссарий
              </a>
              <a href={siteUrls.evaluatorGuide} className="text-muted-foreground hover:text-foreground" target="_blank" rel="noreferrer">
                Оценка за 5 минут
              </a>
              <a href={siteUrls.productFlow} className="text-muted-foreground hover:text-foreground" target="_blank" rel="noreferrer">
                Сквозной сценарий
              </a>
              <a href={siteUrls.githubDocs} className="text-muted-foreground hover:text-foreground" target="_blank" rel="noreferrer">
                Документация
              </a>
              <a href={siteUrls.githubRepo} className="text-muted-foreground hover:text-foreground" target="_blank" rel="noreferrer">
                Исходный код
              </a>
            </div>
            <p className="text-xs text-muted-foreground">Локальный demo: README → docker compose → http://localhost:3000</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
