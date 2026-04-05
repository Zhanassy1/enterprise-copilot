"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type MeOut } from "@/lib/api-client";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { workspaceAppHref } from "@/lib/workspace-path";
import { resolvedWorkspaceSlug } from "@/lib/workspace";
import { useWorkspaceBillingState } from "@/hooks/use-workspace-billing-state";

export function AppShellBanners() {
  const { currentWorkspace } = useWorkspace();
  const billingSlug = resolvedWorkspaceSlug(currentWorkspace);
  const [me, setMe] = useState<MeOut | null>(null);
  const { sub } = useWorkspaceBillingState(currentWorkspace?.id);

  useEffect(() => {
    void api
      .getMe()
      .then(setMe)
      .catch(() => setMe(null));
  }, []);

  const showBilling =
    sub != null &&
    sub.banner_variant !== "none" &&
    Boolean(sub.banner_message);

  const billingTone = sub?.banner_variant === "critical" ? "critical" : "warning";

  return (
    <div className="space-y-0">
      {me?.impersonator_id ? (
        <div
          className="border-b border-amber-500/40 bg-amber-500/15 px-4 py-2 text-center text-sm text-amber-950 dark:text-amber-100"
          role="status"
        >
          Режим поддержки: вы действуете как{" "}
          <span className="font-semibold">{me.email}</span>.{" "}
          <Link href="/login" className="underline underline-offset-2">
            Выйти и завершить сессию
          </Link>
        </div>
      ) : null}
      {showBilling && sub?.banner_message ? (
        <div
          className={
            billingTone === "critical"
              ? "border-b border-destructive/50 bg-destructive/15 px-4 py-2 text-center text-sm text-destructive dark:text-destructive-foreground"
              : "border-b border-amber-400/50 bg-amber-400/20 px-4 py-2 text-center text-sm text-amber-950 dark:text-amber-50"
          }
          role="alert"
        >
          {sub.banner_message}{" "}
          {billingSlug ? (
            <Link href={workspaceAppHref(billingSlug, "/billing")} className="font-medium underline underline-offset-2">
              Открыть биллинг
            </Link>
          ) : (
            <span className="font-medium">Откройте раздел «План и лимиты» после загрузки workspace.</span>
          )}
        </div>
      ) : null}
    </div>
  );
}
