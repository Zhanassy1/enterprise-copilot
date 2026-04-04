"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { api, toErrorMessage, type SubscriptionOut } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { workspaceAppHref } from "@/lib/workspace-path";

const INITIAL_MS = 2000;
const MAX_MS = 8000;
const TIMEOUT_MS = 90_000;

function subscriptionLooksActivated(sub: SubscriptionOut): boolean {
  const slug = (sub.plan_slug || "free").toLowerCase();
  const st = (sub.subscription_status || "").toLowerCase();
  if (slug !== "free") return true;
  return st === "active" || st === "trialing";
}

export default function BillingSuccessPage() {
  const params = useParams();
  const router = useRouter();
  const slug = typeof params?.workspaceSlug === "string" ? params.workspaceSlug : "";
  const [phase, setPhase] = useState<"polling" | "timeout">("polling");

  useEffect(() => {
    if (!slug) return;
    let cancelled = false;
    let delay = INITIAL_MS;
    const started = Date.now();

    const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

    const run = async () => {
      while (!cancelled) {
        try {
          const sub = await api.getBillingSubscription();
          if (subscriptionLooksActivated(sub)) {
            if (!cancelled) {
              toast.success("Подписка активирована");
              router.replace(workspaceAppHref(slug, "/billing"));
            }
            return;
          }
        } catch (e) {
          if (!cancelled) toast.error(toErrorMessage(e));
        }

        if (cancelled) return;
        if (Date.now() - started > TIMEOUT_MS) {
          setPhase("timeout");
          return;
        }

        await sleep(delay);
        delay = Math.min(Math.round(delay * 1.35), MAX_MS);
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, [slug, router]);

  if (!slug) {
    return (
      <div className="flex min-h-[40vh] flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
        Некорректный адрес workspace
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-lg flex-col gap-6 py-12">
      <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
        {phase === "polling" ? (
          <div className="flex items-center gap-3">
            <Loader2 className="h-8 w-8 shrink-0 animate-spin text-primary" aria-hidden />
            <div>
              <h1 className="text-lg font-semibold leading-tight">Подтверждаем оплату</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Ожидаем подтверждение от платёжной системы. Обычно это занимает несколько секунд — не закрывайте вкладку.
              </p>
            </div>
          </div>
        ) : (
          <>
            <h1 className="text-lg font-semibold">Статус ещё обновляется</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Подтверждение иногда приходит с задержкой. Проверьте раздел биллинга через минуту или обновите страницу.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button asChild>
                <a href={workspaceAppHref(slug, "/billing")}>Открыть биллинг</a>
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => window.location.reload()}
              >
                Обновить страницу
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
