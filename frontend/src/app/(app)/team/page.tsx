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

export default function TeamPage() {
  const { currentWorkspace } = useWorkspace();
  const role = currentWorkspace?.role ?? "";
  const admin = isOwnerOrAdmin(role);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Команда и доступ"
        description="Multi-tenant SaaS: участники изолированы по рабочему пространству. Переключатель workspace в сайдбаре задаёт контекст данных и прав."
      />

      <WorkspaceContextStrip area="настройки ниже относятся к этому workspace" />

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
                <span className="font-medium text-foreground">администратор</span> вы отвечаете за безопасность и
                соответствие данных: расширенный аудит, план и лимиты, разбор отказов по квотам. Приглашения и полный UI
                управления участниками описаны в блоке ниже — без имитации готового API.
              </p>
            ) : null}
            {role.toLowerCase() === "member" ? (
              <p>
                <span className="font-medium text-foreground">Участник</span> может загружать и удалять документы (в
                рамках квот), пользоваться поиском и чатом, смотреть очередь индексации. Административные сценарии — у
                владельца и администратора.
              </p>
            ) : null}
            {role.toLowerCase() === "viewer" ? (
              <p>
                <span className="font-medium text-foreground">Наблюдатель</span> — доступ на чтение: документы, поиск, просмотр
                диалогов и summary; загрузка, удаление, новые диалоги и отправка сообщений недоступны (ответ API 403).
              </p>
            ) : null}
            {!["owner", "admin", "member", "viewer"].includes(role.toLowerCase()) ? (
              <p>
                Роль <span className="font-mono text-foreground">{role || "—"}</span> не из стандартного набора — ориентируйтесь на ответы API и журнал аудита.
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="border-dashed">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Users className="h-4 w-4" aria-hidden />
              Участники workspace
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>
              Список пользователей, их роли и история изменений <strong className="text-foreground">не отдаются отдельным публичным API</strong> в
              этой версии продукта. Сейчас клиент знает только <strong className="text-foreground">вашу роль</strong> и имя workspace через{" "}
              <code className="rounded bg-muted px-1">GET /workspaces</code>.
            </p>
            <div className="flex items-start gap-2 rounded-lg bg-muted/50 p-3 text-xs">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-foreground" aria-hidden />
              <p>
                Это намеренный честный placeholder: мы не рисуем фейковую таблицу участников. После появления маршрутов
                (например <code className="font-mono">/workspaces/…/members</code>) этот блок заменится живыми данными.
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
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>
              Поток приглашений (ссылка, срок действия, принятие в workspace) <strong className="text-foreground">в backend не реализован</strong>.
              Ниже — продуктовая кнопка в состоянии «скоро»: она намеренно неактивна и подписана, чтобы не имитировать готовый
              email-flow.
            </p>
            {admin ? (
              <div className="rounded-lg border border-dashed border-muted-foreground/35 bg-muted/30 p-3">
                <Button type="button" variant="secondary" size="sm" className="gap-2" disabled>
                  <Mail className="h-4 w-4 opacity-60" aria-hidden />
                  Пригласить по email
                </Button>
                <p className="mt-2 text-xs">
                  API приглашений нет — после появления маршрутов кнопка станет активной. Сейчас новых участников подключает
                  оператор или выдача учётных записей вне этого UI.
                </p>
              </div>
            ) : null}
            <p className="text-xs">
              Онбординг новых людей сейчас — через учётные данные и выдачу доступа оператором (или будущий модуль
              invitations). См. roadmap в репозитории.
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <UserCog className="h-4 w-4" aria-hidden />
            Что можно сделать сейчас
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
        </CardContent>
      </Card>
    </div>
  );
}
