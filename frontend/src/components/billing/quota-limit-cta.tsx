"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { workspaceAppHref } from "@/lib/workspace-path";
import { isOwnerOrAdmin } from "@/lib/workspace-role";
import { cn } from "@/lib/utils";

type QuotaLimitCtaBannerProps = {
  workspaceSlug: string | undefined;
  role: string | undefined;
  show: boolean;
  className?: string;
};

export function QuotaLimitCtaBanner({ workspaceSlug, role, show, className }: QuotaLimitCtaBannerProps) {
  if (!show || !workspaceSlug) return null;
  const billing = workspaceAppHref(workspaceSlug, "/billing");
  const canManage = isOwnerOrAdmin(role ?? "");

  return (
    <div
      className={cn(
        "rounded-xl border border-primary/35 bg-gradient-to-br from-primary/10 via-background to-background p-4 text-sm shadow-sm",
        className
      )}
      role="status"
    >
      <p className="font-medium text-foreground">Лимит workspace</p>
      <p className="mt-1.5 text-muted-foreground">
        {canManage
          ? "На текущем плане исчерпана квота. Откройте биллинг, чтобы сравнить планы и оформить подписку."
          : "Квота исчерпана. Попросите владельца или администратора workspace повысить план или дождаться сброса периода."}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" asChild>
          <Link href={billing}>План и лимиты</Link>
        </Button>
        {canManage ? (
          <Button size="sm" variant="outline" asChild>
            <Link href="/pricing#pricing-comparison">Тарифы на сайте</Link>
          </Button>
        ) : null}
      </div>
    </div>
  );
}
