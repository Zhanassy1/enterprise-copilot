"use client";

import Link from "next/link";
import { Info, Mail, UserCog, Users } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { WorkspaceContextStrip } from "@/components/workspace/workspace-context-strip";
import { workspaceRoleLabel } from "@/lib/product-terminology";
import { isOwnerOrAdmin } from "@/lib/workspace-role";
import { siteUrls } from "@/lib/site-urls";

const ROLE_MATRIX: { cap: string; owner: string; admin: string; member: string; viewer: string }[] = [
  {
    cap: "Документы: загрузка / удаление",
    owner: "Да",
    admin: "Да",
    member: "Да",
    viewer: "Нет (UI и API)",
  },
  {
    cap: "Поиск и просмотр источников",
    owner: "Да",
    admin: "Да",
    member: "Да",
    viewer: "Да",
  },
  {
    cap: "Чат: новый диалог, отправка сообщений",
    owner: "Да",
    admin: "Да",
    member: "Да",
    viewer: "Нет (UI и API)",
  },
  {
    cap: "Очередь задач индексации (jobs): просмотр",
    owner: "Да",
    admin: "Да",
    member: "Да",
    viewer: "Да",
  },
  {
    cap: "План и лимиты (/billing)",
    owner: "Да",
    admin: "Да",
    member: "Да",
    viewer: "Да",
  },
  {
    cap: "Журнал аудита (расширенные фильтры)",
    owner: "Да",
    admin: "Да",
    member: "По политике API",
    viewer: "По политике API",
  },
  {
    cap: "Пригласить участника (когда будет API)",
    owner: "Будет доступно",
    admin: "Будет доступно",
    member: "Нет",
    viewer: "Нет",
  },
];

export default function TeamPage() {
  const { currentWorkspace } = useWorkspace();
  const role = currentWorkspace?.role ?? "";
  const admin = isOwnerOrAdmin(role);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Команда и доступ"
        description="Рабочее пространство (workspace): изолированный контур данных и ролей. Переключатель в сайдбаре задаёт контекст для API и UI. Участников и приглашения показываем ниже — без фиктивных строк, пока нет отдельных маршрутов."
      />

      <WorkspaceContextStrip area="роль, матрица прав и блоки ниже относятся к этому workspace" />

      {currentWorkspace ? (
        <Card>
          <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3 pb-2">
            <div>
              <CardTitle className="text-base">Ваша роль в этом workspace</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">{currentWorkspace.name}</p>
            </div>
            <Badge variant={admin ? "default" : "secondary"} className="shrink-0">
              {workspaceRoleLabel(role)}
            </Badge>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            {admin ? (
              <p>
                Как <span className="font-medium text-foreground">владелец</span> или{" "}
                <span className="font-medium text-foreground">администратор</span> вы отвечаете за границы данных и
                журнал аудита; после появления API участников сможете выдавать приглашения из этого экрана.
              </p>
            ) : null}
            {role.toLowerCase() === "member" ? (
              <p>
                <span className="font-medium text-foreground">Участник</span> работает с документами в рамках квот, поиском
                и чатом; администрирование workspace — у владельца и администратора.
              </p>
            ) : null}
            {role.toLowerCase() === "viewer" ? (
              <p>
                <span className="font-medium text-foreground">Наблюдатель</span> — чтение и просмотр там, где политика API
                разрешает; изменения данных и отправка сообщений в чате отключены в UI. Подробнее — в матрице ниже и в
                подсказке в сайдбаре.
              </p>
            ) : null}
            {!["owner", "admin", "member", "viewer"].includes(role.toLowerCase()) ? (
              <p>
                Роль <span className="font-mono text-foreground">{role || "—"}</span> вне стандартного набора — ориентируйтесь
                на ответы API и журнал аудита.
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Матрица ролей (справочно)</CardTitle>
          <p className="text-sm text-muted-foreground">
            Согласовано с продуктовым UI и политикой API. Термины:{" "}
            <Link href={siteUrls.githubGlossary} className="underline underline-offset-2" target="_blank" rel="noreferrer">
              docs/product-glossary.md
            </Link>
            .
          </p>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[36rem] border-collapse text-left text-xs">
            <thead>
              <tr className="border-b bg-muted/50 text-[11px] font-medium text-foreground">
                <th className="p-2.5 pr-3">Возможность</th>
                <th className="p-2.5">Владелец</th>
                <th className="p-2.5">Админ</th>
                <th className="p-2.5">Участник</th>
                <th className="p-2.5">Наблюдатель</th>
              </tr>
            </thead>
            <tbody className="text-muted-foreground">
              {ROLE_MATRIX.map((row) => (
                <tr key={row.cap} className="border-b border-border/70">
                  <td className="p-2.5 pr-3 text-foreground">{row.cap}</td>
                  <td className="p-2.5">{row.owner}</td>
                  <td className="p-2.5">{row.admin}</td>
                  <td className="p-2.5">{row.member}</td>
                  <td className="p-2.5">{row.viewer}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="border-dashed">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Users className="h-4 w-4" aria-hidden />
              Участники workspace
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-muted-foreground">
            <p>
              Публичный список пользователей и смена ролей через <strong className="text-foreground">REST API этой версии</strong>{" "}
              не предоставляются — клиент знает только вашу роль и имя workspace из{" "}
              <code className="rounded bg-muted px-1">GET /workspaces</code>.
            </p>
            <div className="overflow-x-auto rounded-lg border bg-card">
              <table className="w-full min-w-[20rem] text-left text-xs">
                <thead>
                  <tr className="border-b bg-muted/40 text-[11px] font-medium text-foreground">
                    <th className="p-2.5">Участник</th>
                    <th className="p-2.5">Роль</th>
                    <th className="p-2.5">Статус</th>
                  </tr>
                </thead>
                <tbody>
                  {currentWorkspace ? (
                    <tr className="border-b border-border/60">
                      <td className="p-2.5 font-medium text-foreground">Вы</td>
                      <td className="p-2.5">
                        <Badge variant="secondary" className="text-[10px]">
                          {workspaceRoleLabel(role)}
                        </Badge>
                      </td>
                      <td className="p-2.5 text-muted-foreground">Активен</td>
                    </tr>
                  ) : null}
                  <tr>
                    <td className="p-3 text-center text-muted-foreground italic" colSpan={3}>
                      Остальные строки появятся после маршрутов вида{" "}
                      <code className="font-mono text-[10px] text-foreground">/workspaces/…/members</code> — без имитации
                      данных.
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="flex items-start gap-2 rounded-lg bg-muted/50 p-3 text-xs">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-foreground" aria-hidden />
              <p>
                Честный product-ready placeholder: таблица показывает структуру SaaS, пока backend не отдаёт колонки «кто в
                workspace».
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className="border-dashed">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Mail className="h-4 w-4" aria-hidden />
              Приглашения по email
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-muted-foreground">
            <p>
              Поток приглашений (письмо, срок ссылки, принятие в workspace) в{" "}
              <strong className="text-foreground">backend не реализован</strong>. Ниже — очередь исходящих приглашений в
              «продуктовом» виде: пусто и явно подписано.
            </p>
            <div className="overflow-x-auto rounded-lg border bg-card">
              <table className="w-full min-w-[20rem] text-left text-xs">
                <thead>
                  <tr className="border-b bg-muted/40 text-[11px] font-medium text-foreground">
                    <th className="p-2.5">Email</th>
                    <th className="p-2.5">Роль</th>
                    <th className="p-2.5">Статус</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="p-3 text-center italic text-muted-foreground" colSpan={3}>
                      Нет данных API — приглашения не создавались
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            {admin ? (
              <div className="rounded-lg border border-dashed border-muted-foreground/35 bg-muted/30 p-3">
                <Button type="button" variant="secondary" size="sm" className="gap-2" disabled>
                  <Mail className="h-4 w-4 opacity-60" aria-hidden />
                  Отправить приглашение
                </Button>
                <p className="mt-2 text-xs">
                  Станет активной после появления маршрутов invitations. Сейчас новых людей в workspace добавляет оператор
                  развёртывания или отдельный онбординг.
                </p>
              </div>
            ) : (
              <p className="rounded-lg border border-border/60 bg-muted/25 p-3 text-xs">
                Отправка приглашений будет доступна <span className="font-medium text-foreground">владельцу</span> и{" "}
                <span className="font-medium text-foreground">администратору</span> после подключения API.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <UserCog className="h-4 w-4" aria-hidden />
            Дальше в продукте
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href="/audit">Журнал аудита workspace</Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link href="/billing">План и лимиты</Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link href="/documents">Документы</Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link href="/pricing#pricing-comparison">Тарифы (маркетинг)</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
