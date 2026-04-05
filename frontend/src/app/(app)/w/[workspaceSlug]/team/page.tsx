"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Info, Mail, UserCog, Users } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { WorkspaceProductContext } from "@/components/workspace/workspace-product-context";
import { PRODUCT_SECTION } from "@/lib/product-terminology";
import { workspaceRoleLabel } from "@/lib/product-terminology";
import { canInviteMembers, isOwnerOrAdmin, normalizeWorkspaceRole } from "@/lib/workspace-role";
import { siteUrls } from "@/lib/site-urls";
import { api, toErrorMessage, type InvitationOut, type WorkspaceMemberOut } from "@/lib/api-client";
import { workspaceAppHref, workspaceRefForApi } from "@/lib/workspace-path";
import { MembersTable } from "@/components/team/members-table";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";

const ROLE_KEYS = ["owner", "admin", "member", "viewer"] as const;

function roleColumnKey(role: string): (typeof ROLE_KEYS)[number] | null {
  const r = normalizeWorkspaceRole(role);
  if (r === "owner" || r === "admin" || r === "member" || r === "viewer") return r;
  return null;
}

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
    cap: "Пригласить участника",
    owner: "Да",
    admin: "Да",
    member: "Нет",
    viewer: "Нет",
  },
];

export default function TeamPage() {
  const { currentWorkspace } = useWorkspace();
  const role = currentWorkspace?.role ?? "";
  const admin = isOwnerOrAdmin(role);
  const colKey = currentWorkspace ? roleColumnKey(currentWorkspace.role) : null;
  const [invites, setInvites] = useState<InvitationOut[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [invLoading, setInvLoading] = useState(false);
  const [members, setMembers] = useState<WorkspaceMemberOut[]>([]);
  const [memLoading, setMemLoading] = useState(false);
  const [myUserId, setMyUserId] = useState<string | null>(null);

  const loadInvites = useCallback(async () => {
    if (!currentWorkspace) return;
    const ref = workspaceRefForApi(currentWorkspace);
    if (!ref) return;
    try {
      const rows = await api.listWorkspaceInvitations(ref);
      setInvites(rows);
    } catch (e) {
      toast.error(toErrorMessage(e));
    }
  }, [currentWorkspace]);

  useEffect(() => {
    void loadInvites();
  }, [loadInvites]);

  useEffect(() => {
    void api.getMe().then((me) => setMyUserId(me.id)).catch(() => setMyUserId(null));
  }, []);

  const loadMembers = useCallback(async () => {
    if (!currentWorkspace) return;
    const ref = workspaceRefForApi(currentWorkspace);
    if (!ref) return;
    setMemLoading(true);
    try {
      const rows = await api.listWorkspaceMembers(ref);
      setMembers(rows);
    } catch (e) {
      toast.error(toErrorMessage(e));
    } finally {
      setMemLoading(false);
    }
  }, [currentWorkspace]);

  useEffect(() => {
    void loadMembers();
  }, [loadMembers]);

  const sendInvite = async () => {
    if (!currentWorkspace) return;
    const ref = workspaceRefForApi(currentWorkspace);
    if (!ref) return;
    setInvLoading(true);
    try {
      await api.createWorkspaceInvitation(ref, inviteEmail.trim(), inviteRole);
      toast.success("Приглашение отправлено");
      setInviteEmail("");
      await loadInvites();
      await loadMembers();
    } catch (e) {
      toast.error(toErrorMessage(e));
    } finally {
      setInvLoading(false);
    }
  };

  const revokeInvite = async (id: string) => {
    if (!currentWorkspace) return;
    const wr = workspaceRefForApi(currentWorkspace);
    if (!wr) return;
    try {
      await api.revokeWorkspaceInvitation(wr, id);
      toast.success("Приглашение отозвано");
      await loadInvites();
    } catch (e) {
      toast.error(toErrorMessage(e));
    }
  };

  const resendInvite = async (id: string) => {
    if (!currentWorkspace) return;
    const wr = workspaceRefForApi(currentWorkspace);
    if (!wr) return;
    try {
      await api.resendWorkspaceInvitation(wr, id);
      toast.success("Письмо отправлено повторно");
      await loadInvites();
    } catch (e) {
      toast.error(toErrorMessage(e));
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={PRODUCT_SECTION.team}
        description={`Одно ${PRODUCT_SECTION.workspace.toLowerCase()} — один изолированный контур: документы, квоты и аудит не пересекаются с другими пространствами. Ниже — участники, ожидающие приглашения и политика ролей.`}
      />

      <WorkspaceProductContext
        area="роль и блоки ниже относятся к этому рабочему пространству"
        viewerDetail="Просмотр участников и списка приглашений доступен; отправка приглашений и смена ролей отключены в интерфейсе для роли «наблюдатель»."
        memberLimit={!canInviteMembers(role) ? "invite" : null}
      />

      <Card className="border-dashed">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Users className="h-4 w-4" aria-hidden />
            Участники workspace
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            Список из <code className="rounded bg-muted px-1">GET /workspaces/…/members</code>. Владелец и администратор
            меняют роли и исключают участников (не владельца и не себя в этом блоке).
          </p>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-muted-foreground">
          {currentWorkspace ? (
            <MembersTable
              workspaceRef={workspaceRefForApi(currentWorkspace)}
              members={members}
              loading={memLoading}
              myUserId={myUserId}
              actorRole={role}
              onUpdated={() => void loadMembers()}
            />
          ) : null}
          <div className="flex items-start gap-2 rounded-lg bg-muted/50 p-3 text-xs">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-foreground" aria-hidden />
            <p>
              Наблюдатель и участник видят список без действий; смена роли и исключение — только у владельца и
              администратора.
            </p>
          </div>
        </CardContent>
      </Card>

      <Card className="border-dashed">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Mail className="h-4 w-4" aria-hidden />
            Ожидающие приглашения
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            Активные приглашения по email. Отправка и отзыв — только у владельца и администратора; остальные роли видят
            список в режиме просмотра.
          </p>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-muted-foreground">
          {!admin ? (
            <p className="rounded-lg border border-border/60 bg-muted/25 p-3 text-xs">
              Управление приглашениями (отправка, повтор письма, отзыв) доступно{" "}
              <span className="font-medium text-foreground">владельцу</span> и{" "}
              <span className="font-medium text-foreground">администратору</span>. Ниже — текущие ожидающие приглашения
              для прозрачности команды.
            </p>
          ) : null}
          <div className="overflow-x-auto rounded-lg border bg-card">
            <table className="w-full min-w-[22rem] text-left text-xs">
              <thead>
                <tr className="border-b bg-muted/40 text-[11px] font-medium text-foreground">
                  <th className="p-2.5">Email</th>
                  <th className="p-2.5">Роль</th>
                  <th className="p-2.5">Истекает</th>
                  {admin ? <th className="p-2.5">Действия</th> : null}
                </tr>
              </thead>
              <tbody>
                {invites.length === 0 ? (
                  <tr>
                    <td className="p-3 text-center text-muted-foreground" colSpan={admin ? 4 : 3}>
                      Нет ожидающих приглашений
                    </td>
                  </tr>
                ) : (
                  invites.map((inv) => (
                    <tr key={inv.id} className="border-b border-border/60">
                      <td className="p-2.5 font-medium text-foreground">{inv.email}</td>
                      <td className="p-2.5">{inv.role}</td>
                      <td className="p-2.5 text-muted-foreground">
                        {inv.expires_at ? new Date(inv.expires_at).toLocaleString("ru-RU") : "—"}
                      </td>
                      {admin ? (
                        <td className="p-2.5">
                          <div className="flex flex-wrap gap-1">
                            <Button type="button" variant="outline" size="sm" onClick={() => void resendInvite(inv.id)}>
                              Ещё раз
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="text-destructive"
                              onClick={() => void revokeInvite(inv.id)}
                            >
                              Отозвать
                            </Button>
                          </div>
                        </td>
                      ) : null}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <UserCog className="h-4 w-4" aria-hidden />
            Политика ролей и действия
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Матрица прав, ваша роль в этом workspace и приглашение коллег (если у вас есть права администратора).
          </p>
        </CardHeader>
        <CardContent className="space-y-6">
          {currentWorkspace ? (
            <div className="flex flex-row flex-wrap items-start justify-between gap-3 rounded-lg border border-border/60 bg-muted/15 p-4">
              <div>
                <p className="text-sm font-medium text-foreground">Ваша роль в этом workspace</p>
                <p className="mt-1 text-sm text-muted-foreground">{currentWorkspace.name}</p>
              </div>
              <Badge variant={admin ? "default" : "secondary"} className="shrink-0">
                {workspaceRoleLabel(role)}
              </Badge>
            </div>
          ) : null}

          <div className="space-y-3 text-sm text-muted-foreground">
            {role.toLowerCase() === "owner" ? (
              <p>
                <span className="font-medium text-foreground">Владелец</span> задаёт верхний уровень доверия к этому
                workspace: политика доступа, контроль событий в аудите и согласование плана; приглашения — из блока ниже.
              </p>
            ) : null}
            {role.toLowerCase() === "admin" ? (
              <p>
                <span className="font-medium text-foreground">Администратор</span> ведёт операционную безопасность и
                разбор инцидентов (аудит, лимиты); приглашения и смена ролей — согласованы с владельцем по политике.
              </p>
            ) : null}
            {role.toLowerCase() === "member" ? (
              <p>
                <span className="font-medium text-foreground">Участник</span> работает с документами в рамках квот,
                поиском и чатом; администрирование workspace — у владельца и администратора.
              </p>
            ) : null}
            {role.toLowerCase() === "viewer" ? (
              <p>
                <span className="font-medium text-foreground">Наблюдатель</span> — чтение и просмотр там, где политика API
                разрешает; изменения данных и отправка сообщений в чате отключены в UI.
              </p>
            ) : null}
            {!["owner", "admin", "member", "viewer"].includes(role.toLowerCase()) ? (
              <p>
                Роль <span className="font-mono text-foreground">{role || "—"}</span> вне стандартного набора — ориентируйтесь
                на ответы API и журнал аудита.
              </p>
            ) : null}
          </div>

          <div>
            <p className="mb-2 text-sm font-medium text-foreground">Матрица ролей</p>
            <p className="mb-3 text-xs text-muted-foreground">
              Одна таблица — ожидаемое поведение продукта; детали:{" "}
              <Link href={siteUrls.githubGlossary} className="underline underline-offset-2" target="_blank" rel="noreferrer">
                docs/product-glossary.md
              </Link>
              .
              {colKey ? (
                <span className="mt-1 block text-xs font-medium text-primary">
                  Подсвечена колонка вашей текущей роли.
                </span>
              ) : null}
            </p>
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full min-w-[36rem] border-collapse text-left text-xs">
                <thead>
                  <tr className="border-b bg-muted/50 text-[11px] font-medium text-foreground">
                    <th className="p-2.5 pr-3">Возможность</th>
                    {ROLE_KEYS.map((k) => (
                      <th
                        key={k}
                        className={`p-2.5 ${colKey === k ? "bg-primary/15 text-primary" : ""}`}
                      >
                        {k === "owner"
                          ? "Владелец"
                          : k === "admin"
                            ? "Администратор"
                            : k === "member"
                              ? "Участник"
                              : "Наблюдатель"}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="text-muted-foreground">
                  {ROLE_MATRIX.map((row) => (
                    <tr key={row.cap} className="border-b border-border/70">
                      <td className="p-2.5 pr-3 text-foreground">{row.cap}</td>
                      {ROLE_KEYS.map((k) => {
                        const val =
                          k === "owner" ? row.owner : k === "admin" ? row.admin : k === "member" ? row.member : row.viewer;
                        return (
                          <td key={k} className={`p-2.5 ${colKey === k ? "bg-primary/10 font-medium text-foreground" : ""}`}>
                            {val}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="space-y-3 border-t border-border/60 pt-4">
            <p className="text-sm font-medium text-foreground">Пригласить по email</p>
            {admin ? (
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <div className="grid flex-1 gap-2 sm:grid-cols-2">
                  <div className="space-y-1">
                    <span className="text-xs font-medium text-foreground">Email</span>
                    <Input
                      type="email"
                      placeholder="colleague@company.com"
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs font-medium text-foreground">Роль</span>
                    <select
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value)}
                    >
                      <option value="admin">Администратор</option>
                      <option value="member">Участник</option>
                      <option value="viewer">Наблюдатель</option>
                    </select>
                  </div>
                </div>
                <Button
                  type="button"
                  size="sm"
                  className="gap-2"
                  disabled={invLoading || !inviteEmail.includes("@")}
                  onClick={() => void sendInvite()}
                >
                  <Mail className="h-4 w-4" aria-hidden />
                  Отправить
                </Button>
              </div>
            ) : (
              <fieldset disabled className="min-w-0 space-y-3 rounded-lg border border-border/60 bg-muted/20 p-3 opacity-80">
                <legend className="sr-only">Приглашение недоступно для вашей роли</legend>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                  <div className="grid flex-1 gap-2 sm:grid-cols-2">
                    <div className="space-y-1">
                      <span className="text-xs font-medium text-foreground">Email</span>
                      <Input type="email" placeholder="colleague@company.com" readOnly value="" />
                    </div>
                    <div className="space-y-1">
                      <span className="text-xs font-medium text-foreground">Роль</span>
                      <select
                        className="flex h-10 w-full cursor-not-allowed rounded-md border border-input bg-muted px-3 py-2 text-sm"
                        value="member"
                        disabled
                      >
                        <option value="member">Участник</option>
                      </select>
                    </div>
                  </div>
                  <Button type="button" size="sm" className="gap-2" disabled>
                    <Mail className="h-4 w-4" aria-hidden />
                    Отправить
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  Отправка приглашений доступна <span className="font-medium text-foreground">владельцу</span> и{" "}
                  <span className="font-medium text-foreground">администратору</span>. Ссылка в письме ведёт на страницу
                  принятия; для существующего пользователя нужен вход под тем же email.
                </p>
              </fieldset>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <UserCog className="h-4 w-4" aria-hidden />
            Дальше в продукте
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href={currentWorkspace?.slug ? workspaceAppHref(currentWorkspace.slug, "/audit") : "/audit"}>
              Журнал аудита workspace
            </Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link href={currentWorkspace?.slug ? workspaceAppHref(currentWorkspace.slug, "/billing") : "/billing"}>
              План и лимиты
            </Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link href={currentWorkspace?.slug ? workspaceAppHref(currentWorkspace.slug, "/documents") : "/documents"}>
              Документы
            </Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link href="/pricing#pricing-comparison">Тарифы (маркетинг)</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
