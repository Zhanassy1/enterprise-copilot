"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type MeOut, type SubscriptionOut } from "@/lib/api-client";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { workspaceAppHref } from "@/lib/workspace-path";

export function AppShellBanners() {
  const { currentWorkspace } = useWorkspace();
  const [me, setMe] = useState<MeOut | null>(null);
  const [sub, setSub] = useState<SubscriptionOut | null>(null);

  useEffect(() => {
    void api
      .getMe()
      .then(setMe)
      .catch(() => setMe(null));
  }, []);

  useEffect(() => {
    if (!currentWorkspace?.id) {
      setSub(null);
      return;
    }
    void api
      .getBillingSubscription()
      .then(setSub)
      .catch(() => setSub(null));
  }, [currentWorkspace?.id]);

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
          <Link
            href={currentWorkspace?.slug ? workspaceAppHref(currentWorkspace.slug, "/billing") : "/billing"}
            className="font-medium underline underline-offset-2"
          >
            Открыть биллинг
          </Link>
        </div>
      ) : null}
    </div>
  );
}
