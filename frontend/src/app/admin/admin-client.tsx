"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, toErrorMessage, type MeOut, type UsageSummaryOut } from "@/lib/api-client";
import { setToken } from "@/lib/auth";
import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ProductErrorBanner } from "@/components/shared/product-error-banner";
import Link from "next/link";

export default function AdminClientPage() {
  const [me, setMe] = useState<MeOut | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [boot, setBoot] = useState(true);
  const [targetUserId, setTargetUserId] = useState("");
  const [wsId, setWsId] = useState("");
  const [usage, setUsage] = useState<UsageSummaryOut | null>(null);
  const [bonusReq, setBonusReq] = useState("");
  const [graceDays, setGraceDays] = useState("7");

  useEffect(() => {
    void api
      .getMe()
      .then((m) => {
        setMe(m);
        setErr(null);
      })
      .catch((e) => setErr(toErrorMessage(e)))
      .finally(() => setBoot(false));
  }, []);

  const impersonate = async () => {
    try {
      const t = await api.adminImpersonate(targetUserId.trim());
      if (t.access_token) setToken(t.access_token);
      toast.success("Режим impersonation активирован");
      window.location.assign("/documents");
    } catch (e) {
      toast.error(toErrorMessage(e));
    }
  };

  const loadUsage = async () => {
    try {
      const u = await api.adminWorkspaceUsage(wsId.trim());
      setUsage(u);
    } catch (e) {
      toast.error(toErrorMessage(e));
    }
  };

  const applyQuota = async () => {
    try {
      const mr = bonusReq.trim() ? Number(bonusReq) : undefined;
      const gd = graceDays.trim() ? Number(graceDays) : undefined;
      await api.adminQuotaAdjust(wsId.trim(), {
        monthly_request_limit: mr != null && !Number.isNaN(mr) ? mr : null,
        extend_grace_days: gd != null && !Number.isNaN(gd) ? gd : null,
      });
      toast.success("Квоты обновлены");
    } catch (e) {
      toast.error(toErrorMessage(e));
    }
  };

  if (boot) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted-foreground">
        Проверка доступа…
      </div>
    );
  }

  if (err && !me) {
    return <ProductErrorBanner message={err} />;
  }

  if (me && !me.is_platform_admin) {
    return (
      <div className="space-y-4">
        <PageHeader title="Админка" description="Платформенный доступ" />
        <div className="rounded-lg border border-amber-500/35 bg-amber-500/10 px-4 py-3 text-sm">
          <p className="font-medium text-foreground">
            Роль «владелец» в workspace и платформенный администратор — разные вещи.
          </p>
          <p className="mt-2 text-muted-foreground">
            Владелец управляет своим пространством (документы, команда, лимиты). Этот раздел — для операторов всей
            установки: impersonation, просмотр usage и ручные квоты по любому workspace.
          </p>
          <p className="mt-2 text-muted-foreground">
            Чтобы открыть доступ себе: добавьте свой email в переменную окружения{" "}
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">PLATFORM_ADMIN_EMAILS</code> в конфиге API
            (через запятую, без пробелов вокруг email) или выставьте в БД флаг{" "}
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">users.is_platform_admin</code> для вашей
            учётной записи. После изменения — перезапуск контейнера/процесса API.
          </p>
        </div>
        <Button variant="outline" asChild>
          <Link href="/documents">Назад в приложение</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Платформенная админка"
        description="Impersonation, просмотр usage и ручные правки квот (только для доверенных администраторов)."
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Impersonation</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="grid flex-1 gap-2">
            <Label htmlFor="uid">User ID</Label>
            <Input id="uid" value={targetUserId} onChange={(e) => setTargetUserId(e.target.value)} placeholder="uuid" />
          </div>
          <Button type="button" onClick={() => void impersonate()} disabled={targetUserId.length < 10}>
            Войти как пользователь
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Usage workspace</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="grid flex-1 gap-2">
              <Label htmlFor="ws">Workspace ID</Label>
              <Input id="ws" value={wsId} onChange={(e) => setWsId(e.target.value)} placeholder="uuid" />
            </div>
            <Button type="button" variant="secondary" onClick={() => void loadUsage()}>
              Загрузить
            </Button>
          </div>
          {usage ? (
            <pre className="max-h-64 overflow-auto rounded-lg bg-muted p-3 text-xs">{JSON.stringify(usage, null, 2)}</pre>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Ручная правка квот</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2 sm:grid-cols-2">
            <div>
              <Label htmlFor="mr">Лимит запросов/мес (абсолют)</Label>
              <Input id="mr" value={bonusReq} onChange={(e) => setBonusReq(e.target.value)} placeholder="например 50000" />
            </div>
            <div>
              <Label htmlFor="gd">Продлить grace (дней)</Label>
              <Input id="gd" value={graceDays} onChange={(e) => setGraceDays(e.target.value)} />
            </div>
          </div>
          <Button type="button" variant="outline" onClick={() => void applyQuota()} disabled={wsId.length < 10}>
            Применить к workspace выше
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
