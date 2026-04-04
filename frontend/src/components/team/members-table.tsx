"use client";

import { useState } from "react";
import { toast } from "sonner";
import { api, toErrorMessage, type WorkspaceMemberOut } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { workspaceRoleLabel } from "@/lib/product-terminology";
import { normalizeWorkspaceRole } from "@/lib/workspace-role";

function roleSelectOptions(actorRole: string, targetRole: string): string[] {
  const a = normalizeWorkspaceRole(actorRole);
  const t = normalizeWorkspaceRole(targetRole);
  if (a === "owner") return ["admin", "member", "viewer"];
  if (a === "admin") {
    if (t === "admin" || t === "owner") return [];
    return ["member", "viewer"];
  }
  return [];
}

function canManageOthersRow(actorRole: string, member: WorkspaceMemberOut, myUserId: string | null): boolean {
  const a = normalizeWorkspaceRole(actorRole);
  if (a !== "owner" && a !== "admin") return false;
  const t = normalizeWorkspaceRole(member.role);
  if (t === "owner") return false;
  if (myUserId && member.user_id === myUserId) return false;
  if (a === "admin" && t === "admin") return false;
  return true;
}

export function MembersTable({
  workspaceRef,
  members,
  loading,
  myUserId,
  actorRole,
  onUpdated,
}: {
  workspaceRef: string;
  members: WorkspaceMemberOut[];
  loading: boolean;
  myUserId: string | null;
  actorRole: string;
  onUpdated: () => void;
}) {
  const [roleSaving, setRoleSaving] = useState<string | null>(null);
  const [kickTarget, setKickTarget] = useState<WorkspaceMemberOut | null>(null);
  const [kickBusy, setKickBusy] = useState(false);

  const changeRole = async (userId: string, newRole: string) => {
    setRoleSaving(userId);
    try {
      await api.updateWorkspaceMemberRole(workspaceRef, userId, newRole);
      toast.success("Роль обновлена");
      onUpdated();
    } catch (e) {
      toast.error(toErrorMessage(e));
    } finally {
      setRoleSaving(null);
    }
  };

  const confirmKick = async () => {
    if (!kickTarget) return;
    setKickBusy(true);
    try {
      await api.removeWorkspaceMember(workspaceRef, kickTarget.user_id);
      toast.success("Участник исключён");
      setKickTarget(null);
      onUpdated();
    } catch (e) {
      toast.error(toErrorMessage(e));
    } finally {
      setKickBusy(false);
    }
  };

  return (
    <>
      <div className="overflow-x-auto rounded-lg border bg-card">
        <table className="w-full min-w-[28rem] text-left text-xs">
          <thead>
            <tr className="border-b bg-muted/40 text-[11px] font-medium text-foreground">
              <th className="p-2.5">Участник</th>
              <th className="p-2.5">Роль</th>
              <th className="p-2.5">В составе с</th>
              <th className="p-2.5 text-right">Действия</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td className="p-3 text-muted-foreground" colSpan={4}>
                  Загрузка…
                </td>
              </tr>
            ) : members.length === 0 ? (
              <tr>
                <td className="p-3 text-center text-muted-foreground" colSpan={4}>
                  Нет данных
                </td>
              </tr>
            ) : (
              members.map((m) => {
                const label = (m.full_name && m.full_name.trim()) || m.email;
                const opts = roleSelectOptions(actorRole, m.role);
                const manage = canManageOthersRow(actorRole, m, myUserId);
                const showSelect = manage && opts.length > 0;
                return (
                  <tr key={m.user_id} className="border-b border-border/60">
                    <td className="p-2.5">
                      <div className="font-medium text-foreground">{label}</div>
                      {m.full_name ? <div className="text-[10px] text-muted-foreground">{m.email}</div> : null}
                    </td>
                    <td className="p-2.5">
                      {showSelect ? (
                        <select
                          className="h-9 max-w-[11rem] rounded-md border border-input bg-background px-2 py-1 text-xs"
                          value={normalizeWorkspaceRole(m.role)}
                          disabled={roleSaving === m.user_id}
                          onChange={(e) => void changeRole(m.user_id, e.target.value)}
                        >
                          {opts.map((r) => (
                            <option key={r} value={r}>
                              {workspaceRoleLabel(r)}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <Badge variant="secondary" className="text-[10px]">
                          {workspaceRoleLabel(m.role)}
                        </Badge>
                      )}
                    </td>
                    <td className="p-2.5 text-muted-foreground">
                      {m.joined_at ? new Date(m.joined_at).toLocaleString("ru-RU") : "—"}
                    </td>
                    <td className="p-2.5 text-right">
                      {manage ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="text-destructive"
                          onClick={() => setKickTarget(m)}
                        >
                          Исключить
                        </Button>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <AlertDialog open={kickTarget !== null} onOpenChange={(o) => !o && setKickTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Исключить участника?</AlertDialogTitle>
            <AlertDialogDescription>
              {kickTarget
                ? `Пользователь ${kickTarget.email} потеряет доступ к этому workspace.`
                : null}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={kickBusy}>Отмена</AlertDialogCancel>
            <Button
              type="button"
              variant="destructive"
              disabled={kickBusy}
              onClick={() => void confirmKick()}
            >
              Исключить
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
