"use client";

import Link from "next/link";
import { Eye } from "lucide-react";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { isViewer } from "@/lib/workspace-role";

/** Краткая подсказка в сайдбаре / моб. меню: роль наблюдатель (viewer) без дублирования логики API. */
export function NavRoleHint() {
  const { currentWorkspace } = useWorkspace();
  if (!isViewer(currentWorkspace?.role)) return null;
  return (
    <div className="mx-1 mb-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-2.5 py-2 text-[11px] leading-snug text-amber-950 dark:text-amber-50">
      <p className="flex items-start gap-1.5 font-medium text-amber-900 dark:text-amber-100">
        <Eye className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
        Наблюдатель (viewer)
      </p>
      <p className="mt-1 text-amber-900/90 dark:text-amber-100/90">
        Загрузка и удаление документов, новые диалоги и отправка в чате недоступны. Поиск и просмотр — доступны в рамках
        политики API.
      </p>
      <p className="mt-1.5">
        <Link href="/team" className="font-medium text-foreground underline underline-offset-2">
          Команда и доступ
        </Link>
      </p>
    </div>
  );
}
