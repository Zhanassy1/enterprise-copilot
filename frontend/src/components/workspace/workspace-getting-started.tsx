"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, FileUp, Users, CreditCard } from "lucide-react";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { workspaceAppHref } from "@/lib/workspace-path";
import { canInviteMembers, canManageBillingCheckout, canWriteInWorkspace } from "@/lib/workspace-role";
import { PRODUCT_SECTION } from "@/lib/product-terminology";

/** Скрыть блок: `NEXT_PUBLIC_SHOW_PRODUCT_DEMOS=0` в env. */
function demosEnabled(): boolean {
  return process.env.NEXT_PUBLIC_SHOW_PRODUCT_DEMOS !== "0";
}

/**
 * Компактные сквозные сценарии для workspace-маршрутов (/w/:slug/...).
 */
export function WorkspaceGettingStarted() {
  const pathname = usePathname();
  const { currentWorkspace } = useWorkspace();

  if (!demosEnabled() || !pathname?.startsWith("/w/") || !currentWorkspace?.slug) {
    return null;
  }

  const slug = currentWorkspace.slug;
  const role = currentWorkspace.role;
  const canBill = canManageBillingCheckout(role);
  const canInvite = canInviteMembers(role);
  const canUpload = canWriteInWorkspace(role);

  return (
    <details className="group mb-6 rounded-xl border border-dashed border-primary/30 bg-gradient-to-br from-primary/5 to-transparent open:pb-4">
      <summary className="cursor-pointer list-none px-4 py-3 text-sm font-medium text-foreground marker:content-none [&::-webkit-details-marker]:hidden">
        <span className="inline-flex items-center gap-2">
          <ChevronRight className="h-4 w-4 shrink-0 transition-transform group-open:rotate-90" aria-hidden />
          Быстрые сценарии: команда, план, документы
        </span>
      </summary>
      <ol className="list-none space-y-3 border-t border-border/60 px-4 pt-3 text-sm text-muted-foreground">
        <li className="flex gap-3">
          <Users className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
          <div>
            <span className="font-medium text-foreground">Присоединиться к {PRODUCT_SECTION.workspace.toLowerCase()}</span>
            <p className="mt-0.5">
              Приглашение по email и роль — на{" "}
              <Link href={workspaceAppHref(slug, "/team")} className="text-primary underline-offset-2 hover:underline">
                {PRODUCT_SECTION.team}
              </Link>
              .{" "}
              {!canInvite ? (
                <span className="text-muted-foreground">(Отправка приглашений — у владельца или администратора.)</span>
              ) : null}
            </p>
          </div>
        </li>
        <li className="flex gap-3">
          <CreditCard className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
          <div>
            <span className="font-medium text-foreground">План и квоты</span>
            <p className="mt-0.5">
              Сравнение лимитов и оформление подписки —{" "}
              <Link href={workspaceAppHref(slug, "/billing")} className="text-primary underline-offset-2 hover:underline">
                {PRODUCT_SECTION.planAndQuotas}
              </Link>
              .{" "}
              {!canBill ? (
                <span className="text-muted-foreground">(Оформление оплаты — у владельца или администратора.)</span>
              ) : null}
            </p>
          </div>
        </li>
        <li className="flex gap-3">
          <FileUp className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
          <div>
            <span className="font-medium text-foreground">Загрузка и индексация</span>
            <p className="mt-0.5">
              {canUpload ? (
                <>
                  Загрузите файл на{" "}
                  <Link href={workspaceAppHref(slug, "/documents")} className="text-primary underline-offset-2 hover:underline">
                    Документы
                  </Link>
                  , затем проверьте статус в{" "}
                  <Link href={workspaceAppHref(slug, "/jobs")} className="text-primary underline-offset-2 hover:underline">
                    {PRODUCT_SECTION.ingestionQueue}
                  </Link>
                  .
                </>
              ) : (
                <>
                  У роли «наблюдатель» загрузка недоступна — откройте{" "}
                  <Link href={workspaceAppHref(slug, "/jobs")} className="text-primary underline-offset-2 hover:underline">
                    {PRODUCT_SECTION.ingestionQueue}
                  </Link>{" "}
                  или попросите коллегу загрузить файл.
                </>
              )}
            </p>
          </div>
        </li>
      </ol>
    </details>
  );
}
