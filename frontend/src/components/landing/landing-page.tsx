import Link from "next/link";
import {
  Activity,
  ArrowRight,
  Building2,
  Gauge,
  Layers,
  Shield,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { siteUrls } from "@/lib/site-urls";

const features = [
  {
    title: "Изоляция workspace",
    body: "Документы и векторный индекс разделены по рабочим пространствам; доступ по ролям владелец / администратор / участник / наблюдатель.",
    icon: Building2,
  },
  {
    title: "Асинхронная индексация",
    body: "Загрузка не блокирует HTTP: парсинг, чанки и embeddings выполняет worker (Celery), статусы документа и job видны в приложении.",
    icon: Layers,
  },
  {
    title: "Квоты и планы",
    body: "Лимиты по запросам, токенам LLM, объёму загрузок и параллельным job — согласованы с тарифом workspace (free / pro / team).",
    icon: Gauge,
  },
  {
    title: "Безопасность и аудит",
    body: "JWT, refresh rotation, события аудита в workspace; готовность к политике секретов и reverse proxy в production.",
    icon: Shield,
  },
  {
    title: "Поиск и RAG-чат",
    body: "Семантический поиск и ответы с источниками по загруженным PDF, DOCX и тексту.",
    icon: Sparkles,
  },
  {
    title: "Наблюдаемость",
    body: "Структурные логи, X-Request-Id, метрики и runbook для операций — см. документацию репозитория.",
    icon: Activity,
  },
];

const plans = [
  {
    name: "Free",
    hint: "Старт и оценка",
    rows: [
      "2 000 запросов / мес",
      "2M токенов LLM / мес",
      "512 MiB загрузок / мес",
      "до 50 документов",
      "2 параллельных job",
    ],
  },
  {
    name: "Pro",
    hint: "Команды и нагрузка",
    highlight: true,
    rows: [
      "50 000 запросов / мес",
      "20M токенов / мес",
      "5 GiB загрузок / мес",
      "до 10 000 документов",
      "8 параллельных job",
    ],
  },
  {
    name: "Team",
    hint: "Масштаб",
    rows: [
      "500 000 запросов / мес",
      "200M токенов / мес",
      "50 GiB загрузок / мес",
      "документы без жёсткого потолка",
      "32 параллельных job",
    ],
  },
];

export function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b bg-card/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <span className="text-lg font-semibold tracking-tight">Enterprise Copilot</span>
          <nav className="flex items-center gap-2 sm:gap-3">
            <a
              href={siteUrls.githubDocs}
              className="hidden text-sm text-muted-foreground hover:text-foreground sm:inline"
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

      <section className="relative overflow-hidden border-b bg-gradient-to-b from-muted/40 to-background px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-sm font-medium uppercase tracking-widest text-muted-foreground">
            Multi-tenant AI copilot для документов
          </p>
          <h1 className="mt-4 text-4xl font-bold tracking-tight sm:text-5xl">
            Ответы и поиск по корпоративным PDF и DOCX — с изоляцией данных и квотами
          </h1>
          <p className="mt-6 text-lg text-muted-foreground">
            Загрузка в object storage, асинхронная индексация, семантический поиск и чат с указанием источников. Платформа
            учитывает план workspace: лимиты, аудит и готовность к production-деплою.
          </p>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            <Button size="lg" asChild>
              <Link href="/register">
                Начать бесплатно
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link href="/login">Уже есть аккаунт</Link>
            </Button>
          </div>
          <p className="mt-6 text-xs text-muted-foreground">
            Оплата через внешнего провайдера (например Stripe) в roadmap — сейчас планы и usage отражаются через API и UI без
            live-биллинга.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <h2 className="text-center text-2xl font-semibold">Возможности платформы</h2>
        <p className="mx-auto mt-2 max-w-2xl text-center text-sm text-muted-foreground">
          Не только API: единый жизненный цикл auth → workspace → загрузка → job → поиск и чат → контроль лимитов и аудита.
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

      <section className="border-y bg-muted/30 px-4 py-16 sm:px-6">
        <div className="mx-auto max-w-6xl">
          <h2 className="text-2xl font-semibold">Архитектура и ценность</h2>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
            Клиент (Next.js) обращается к FastAPI с заголовком <code className="rounded bg-muted px-1">X-Workspace-Id</code>
            . Тяжёлая работа вынесена в Celery: после commit метаданных документа и job задача попадает в очередь Redis. Векторы
            и чанки хранятся в PostgreSQL (pgvector), файлы — в local или S3. Это снижает задержку API и упрощает горизонтальное
            масштабирование.
          </p>
          <ul className="mt-6 list-inside list-disc space-y-2 text-sm text-muted-foreground">
            <li>Квоты и HTTP rate limits масштабируются от плана workspace.</li>
            <li>События аудита и отказ по квоте доступны в API и в UI «Аудит» (для ролей с доступом).</li>
            <li>Метрики, логи и runbook описаны в репозитории для эксплуатации.</li>
          </ul>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <h2 className="text-center text-2xl font-semibold">Тарифы (ориентиры)</h2>
        <p className="mx-auto mt-2 max-w-2xl text-center text-sm text-muted-foreground">
          Значения совпадают с лимитами по умолчанию в backend; точные цифры для вашего workspace — на странице «План и лимиты»
          после входа. Внешний биллинг подключается отдельно.
        </p>
        <div className="mt-10 grid gap-6 lg:grid-cols-3">
          {plans.map((p) => (
            <Card
              key={p.name}
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
                  {p.rows.map((row) => (
                    <li key={row}>• {row}</li>
                  ))}
                </ul>
                <Button className="mt-6 w-full" variant={p.highlight ? "default" : "outline"} asChild>
                  <Link href="/register">Выбрать {p.name}</Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="border-t bg-muted/20 px-4 py-12 sm:px-6">
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-4 text-center sm:flex-row sm:justify-between sm:text-left">
          <div>
            <h2 className="text-xl font-semibold">Готовы подключить документы?</h2>
            <p className="mt-1 text-sm text-muted-foreground">Регистрация и workspace займут пару минут.</p>
          </div>
          <Button size="lg" asChild>
            <Link href="/register">Создать аккаунт</Link>
          </Button>
        </div>
      </section>

      <footer className="border-t bg-card px-4 py-10 sm:px-6">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="font-semibold">Enterprise Copilot</p>
            <p className="mt-1 text-xs text-muted-foreground">AI-платформа для документов с multi-tenant изоляцией.</p>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
            <a href={siteUrls.githubDocs} className="text-muted-foreground hover:text-foreground" target="_blank" rel="noreferrer">
              Документация (GitHub)
            </a>
            <a href={siteUrls.githubReadme} className="text-muted-foreground hover:text-foreground" target="_blank" rel="noreferrer">
              README
            </a>
            <a href={siteUrls.githubRepo} className="text-muted-foreground hover:text-foreground" target="_blank" rel="noreferrer">
              Исходный код
            </a>
            <span className="text-muted-foreground">Demo: локальный UI после docker compose (см. README)</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
