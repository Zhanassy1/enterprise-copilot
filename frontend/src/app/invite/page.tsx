"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { api, toErrorMessage, type InviteValidateOut, type MeOut } from "@/lib/api-client";
import { getToken, setToken } from "@/lib/auth";
import { setWorkspaceId } from "@/lib/workspace";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2 } from "lucide-react";

function InviteContent() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [info, setInfo] = useState<InviteValidateOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [session, setSession] = useState<MeOut | null | undefined>(undefined);

  useEffect(() => {
    if (!getToken()) {
      setSession(null);
      return;
    }
    void api
      .getMe()
      .then(setSession)
      .catch(() => setSession(null));
  }, []);

  useEffect(() => {
    if (!token || token.length < 16) {
      setLoading(false);
      return;
    }
    void api
      .validateInvite(token)
      .then(setInfo)
      .catch((e) => toast.error(toErrorMessage(e)))
      .finally(() => setLoading(false));
  }, [token]);

  const acceptLoggedIn = async () => {
    setSubmitting(true);
    try {
      const t = await api.acceptInvite(token, null, null);
      setToken(t.access_token);
      if (info?.workspace_id) setWorkspaceId(info.workspace_id);
      toast.success("Приглашение принято");
      router.replace("/documents");
    } catch (e) {
      toast.error(toErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  const acceptNew = async () => {
    setSubmitting(true);
    try {
      const t = await api.acceptInvite(token, password, fullName || null);
      setToken(t.access_token);
      if (info?.workspace_id) setWorkspaceId(info.workspace_id);
      toast.success("Аккаунт создан, вы добавлены в workspace");
      router.replace("/documents");
    } catch (e) {
      toast.error(toErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-muted-foreground">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (!token || token.length < 16 || !info) {
    return (
      <Card className="mx-auto mt-12 max-w-md shadow-md">
        <CardHeader>
          <CardTitle>Приглашение недействительно</CardTitle>
        </CardHeader>
        <CardFooter>
          <Button variant="outline" asChild>
            <Link href="/login">На страницу входа</Link>
          </Button>
        </CardFooter>
      </Card>
    );
  }

  const loginHref = `/login?next=${encodeURIComponent(`/invite?token=${encodeURIComponent(token)}`)}`;

  return (
    <Card className="mx-auto mt-12 max-w-md shadow-md">
      <CardHeader>
        <CardTitle className="text-xl">Приглашение в workspace</CardTitle>
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{info.workspace_name}</span> — роль{" "}
          <span className="font-mono text-xs">{info.role}</span>
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Email: <span className="text-foreground">{info.email}</span>
        </p>
        {info.user_exists ? (
          <div className="space-y-3">
            {session === undefined ? (
              <p className="text-sm text-muted-foreground">Проверка сессии…</p>
            ) : session && session.email.toLowerCase() === info.email.toLowerCase() ? (
              <>
                <p className="text-sm">Вы вошли как {session.email}. Примите приглашение.</p>
                <Button className="w-full" disabled={submitting} onClick={() => void acceptLoggedIn()}>
                  {submitting && <Loader2 className="animate-spin" />}
                  Принять приглашение
                </Button>
              </>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">
                  Сначала войдите под {info.email}, затем откройте эту ссылку снова или нажмите ниже.
                </p>
                <Button className="w-full" asChild>
                  <Link href={loginHref}>Войти</Link>
                </Button>
              </>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="full_name">Имя</Label>
              <Input id="full_name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Пароль (мин. 8 символов)</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            <Button
              className="w-full"
              disabled={submitting || password.length < 8}
              onClick={() => void acceptNew()}
            >
              {submitting && <Loader2 className="animate-spin" />}
              Создать аккаунт и войти
            </Button>
          </div>
        )}
      </CardContent>
      <CardFooter className="text-sm text-muted-foreground">
        <Link href="/login" className="underline-offset-4 hover:underline">
          Уже вошли? Страница входа
        </Link>
      </CardFooter>
    </Card>
  );
}

export default function InvitePage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <InviteContent />
    </Suspense>
  );
}
