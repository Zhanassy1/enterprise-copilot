"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api-client";
import { getToken } from "@/lib/auth";
import { normalizePlanSlug } from "@/lib/plan-labels";
import { workspaceAppHref } from "@/lib/workspace-path";
import { getWorkspaceSlug } from "@/lib/workspace";
import { canManageBillingCheckout } from "@/lib/workspace-role";

const TIER: Record<string, number> = { free: 0, pro: 1, team: 2 };

export interface PricingPlanActionsProps {
  planSlug: string;
  planName: string;
  highlight?: boolean;
}

export function PricingPlanActions({ planSlug, planName, highlight }: PricingPlanActionsProps) {
  const [phase, setPhase] = useState<"loading" | "anon" | "authed">("loading");
  const [workspaceSlug, setWorkspaceSlug] = useState<string | null>(null);
  const [workspaceRole, setWorkspaceRole] = useState<string | null>(null);
  const [userPlan, setUserPlan] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setPhase("anon");
      return;
    }
    void (async () => {
      try {
        const workspaces = await api.listWorkspaces();
        if (!workspaces.length) {
          setPhase("anon");
          return;
        }
        const w = workspaces[0];
        setWorkspaceSlug(w.slug);
        setWorkspaceRole(w.role);
        const sub = await api.getBillingSubscription(w.id);
        setUserPlan(normalizePlanSlug(sub.plan_slug));
        setPhase("authed");
      } catch {
        setPhase("anon");
      }
    })();
  }, []);

  const card = normalizePlanSlug(planSlug);
  const userTier = userPlan ? (TIER[userPlan] ?? 0) : 0;
  const cardTier = TIER[card] ?? 0;

  if (phase === "loading") {
    return (
      <Button className="w-full" variant="outline" disabled>
        …
      </Button>
    );
  }

  if (phase === "anon") {
    return (
      <>
        <Button className="w-full" variant={highlight ? "default" : "outline"} asChild>
          <Link href="/register">
            Начать с {planName}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
        <p className="text-center text-xs text-muted-foreground">
          <Link href="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
            Уже в аккаунте — смотреть фактические лимиты
          </Link>
        </p>
      </>
    );
  }

  const slugForBilling = workspaceSlug ?? getWorkspaceSlug();
  const billingBase = slugForBilling ? workspaceAppHref(slugForBilling, "/billing") : "/billing";
  const billingPayment = `${billingBase}#billing-payment-section`;
  const isCurrent = userPlan === card;
  const canUpgradeHere = cardTier > userTier;
  const canCheckout = canManageBillingCheckout(workspaceRole);

  return (
    <div className="flex w-full flex-col gap-2">
      {isCurrent ? (
        <Button type="button" className="w-full" variant="secondary" disabled>
          Current plan
        </Button>
      ) : canUpgradeHere ? (
        canCheckout ? (
          <Button className="w-full" asChild>
            <Link href={billingPayment}>Upgrade</Link>
          </Button>
        ) : (
          <Button
            type="button"
            className="w-full"
            disabled
            title="Оформление подписки доступно владельцу и администратору workspace"
          >
            Upgrade
          </Button>
        )
      ) : (
        <Button className="w-full" variant="outline" asChild>
          <Link href={billingBase}>Открыть план и лимиты</Link>
        </Button>
      )}
      <Button className="w-full" variant={isCurrent && !canUpgradeHere ? "default" : "outline"} asChild>
        <Link href={billingBase}>Manage billing</Link>
      </Button>
    </div>
  );
}
