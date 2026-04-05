"use client";

import { Info } from "lucide-react";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { normalizeWorkspaceRole } from "@/lib/workspace-role";

type Variant = "invite" | "checkout";

const COPY: Record<Variant, { title: string; body: string }> = {
  invite: {
    title: "Роль «участник»",
    body: "Отправка приглашений доступна владельцу и администратору. Попросите их добавить коллегу в это рабочее пространство.",
  },
  checkout: {
    title: "Роль «участник»",
    body: "Оформление или смена платного плана доступны владельцу и администратору. Вы по-прежнему видите план и расход квот.",
  },
};

/** Нейтральная полоса для member, где админские действия скрыты не только на backend. */
export function WorkspaceMemberLimitedBanner({ variant }: { variant: Variant }) {
  const { currentWorkspace } = useWorkspace();
  if (normalizeWorkspaceRole(currentWorkspace?.role) !== "member") return null;
  const { title, body } = COPY[variant];
  return (
    <div
      className="flex gap-2 rounded-xl border border-sky-500/40 bg-sky-500/10 px-3 py-2.5 text-sm text-sky-950 dark:text-sky-50"
      role="status"
    >
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-sky-700 dark:text-sky-200" aria-hidden />
      <div>
        <p className="font-medium text-sky-900 dark:text-sky-100">{title}</p>
        <p className="mt-0.5 text-xs leading-relaxed text-sky-900/90 dark:text-sky-100/90">{body}</p>
      </div>
    </div>
  );
}
