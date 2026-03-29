import Link from "next/link";
import { Button } from "@/components/ui/button";
import { siteUrls } from "@/lib/site-urls";

export function MarketingShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-50 border-b bg-card/90 backdrop-blur supports-[backdrop-filter]:bg-card/75">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link href="/" className="text-lg font-semibold tracking-tight">
            Enterprise Copilot
          </Link>
          <nav className="flex items-center gap-1 sm:gap-2">
            <Link
              href="/#demo-quick-1min"
              className="hidden rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground sm:inline"
            >
              Демо 1′
            </Link>
            <Link
              href="/pricing"
              className="hidden rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground sm:inline"
            >
              Тарифы
            </Link>
            <a
              href={siteUrls.evaluatorGuide}
              className="hidden rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground md:inline"
              target="_blank"
              rel="noreferrer"
            >
              5 минут
            </a>
            <a
              href={siteUrls.githubDocs}
              className="hidden rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground lg:inline"
              target="_blank"
              rel="noreferrer"
            >
              Docs
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
      {children}
      <footer className="border-t bg-card px-4 py-10 sm:px-6">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="font-semibold">Enterprise Copilot</p>
            <p className="mt-1 max-w-sm text-xs text-muted-foreground">
              AI по вашим документам: workspace, роли, план и квоты, журнал аудита — в одном веб-приложении.
            </p>
          </div>
          <div className="flex flex-col gap-3 text-sm lg:items-end">
            <div className="flex flex-wrap gap-x-5 gap-y-2">
              <Link href="/pricing" className="text-muted-foreground hover:text-foreground">
                Тарифы
              </Link>
              <a href={siteUrls.githubGlossary} className="text-muted-foreground hover:text-foreground" target="_blank" rel="noreferrer">
                Глоссарий
              </a>
              <a href={siteUrls.demoQuick1Min} className="text-muted-foreground hover:text-foreground" target="_blank" rel="noreferrer">
                Демо 1 мин (README)
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
                GitHub
              </a>
            </div>
            <p className="text-xs text-muted-foreground">Локально: docker compose → http://localhost:3000</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
