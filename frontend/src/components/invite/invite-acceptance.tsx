"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { api, toErrorMessage, type InviteValidateOut, type MeOut } from "@/lib/api-client";
import { clearToken, getToken, setToken } from "@/lib/auth";
import { setWorkspaceId } from "@/lib/workspace";
import { invitePathForToken } from "@/lib/invite-nav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Loader2, ShieldCheck } from "lucide-react";

function formatExpires(iso: string | null): string | null {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return null;
    return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return null;
  }
}

export function InviteAcceptance({ token }: { token: string }) {
  const router = useRouter();
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

  const inviteReturnPath = invitePathForToken(token);
  const loginHref = `/login?next=${encodeURIComponent(inviteReturnPath)}`;
  const registerHref =
    info && token.length >= 16
      ? `/register?invite=${encodeURIComponent(token)}&email=${encodeURIComponent(info.email)}`
      : `/register?invite=${encodeURIComponent(token)}`;

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 text-muted-foreground">
        <Loader2 className="h-10 w-10 animate-spin text-indigo-400" />
      </div>
    );
  }

  if (!token || token.length < 16 || !info) {
    return (
      <div className="relative min-h-screen overflow-hidden bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 px-4 py-16">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-600/20 via-transparent to-transparent" />
        <div className="relative mx-auto max-w-md rounded-2xl border border-white/10 bg-slate-900/80 p-8 shadow-2xl backdrop-blur">
          <h1 className="text-xl font-semibold tracking-tight text-white">Приглашение недействительно</h1>
          <p className="mt-2 text-sm text-slate-400">Ссылка устарела или указан неверный токен.</p>
          <Button className="mt-6" variant="secondary" asChild>
            <Link href="/login">На страницу входа</Link>
          </Button>
        </div>
      </div>
    );
  }

  const expiresLabel = formatExpires(info.expires_at);
  const emailsMatch =
    session != null && session.email.toLowerCase() === info.email.toLowerCase();

  return (
    <div className="relative min-h-screen overflow-hidden bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 px-4 py-10 sm:py-16">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-600/25 via-transparent to-transparent" />
      <div className="pointer-events-none absolute -left-32 top-1/3 h-96 w-96 rounded-full bg-violet-600/10 blur-3xl" />
      <div className="pointer-events-none absolute -right-32 bottom-1/4 h-96 w-96 rounded-full bg-cyan-600/10 blur-3xl" />

      <div className="relative mx-auto max-w-lg">
        <div className="mb-8 text-center">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-slate-300 backdrop-blur">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
            Защищённое приглашение
          </div>
          <h1 className="text-balance text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Присоединиться к {info.workspace_name}
          </h1>
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
            <Badge variant="secondary" className="border-white/10 bg-white/10 text-slate-100">
              {info.role}
            </Badge>
            {expiresLabel && (
              <span className="text-sm text-slate-400">до {expiresLabel}</span>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-slate-900/80 p-6 shadow-2xl backdrop-blur sm:p-8">
          <p className="text-sm leading-relaxed text-slate-400">
            Администратор workspace пригласил указанный ниже адрес. Принять может только пользователь с этим email — так
            мы защищаем доступ к данным команды.
          </p>

          <div className="mt-6 space-y-2">
            <Label className="text-slate-300">Email приглашения</Label>
            <div className="rounded-lg border border-white/10 bg-slate-950/50 px-3 py-2.5 font-mono text-sm text-slate-100">
              {info.email}
            </div>
          </div>

          {info.user_exists ? (
            <div className="mt-8 space-y-4">
              {session === undefined ? (
                <p className="text-sm text-slate-400">Проверка сессии…</p>
              ) : emailsMatch ? (
                <>
                  <p className="text-sm text-slate-300">
                    Вы вошли как <span className="font-medium text-white">{session.email}</span>. Нажмите, чтобы
                    присоединиться к workspace.
                  </p>
                  <Button
                    className="h-11 w-full bg-indigo-600 text-white hover:bg-indigo-500"
                    disabled={submitting}
                    onClick={() => void acceptLoggedIn()}
                  >
                    {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Принять приглашение
                  </Button>
                </>
              ) : session ? (
                <>
                  <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 text-sm text-amber-100/90">
                    <p className="font-medium text-amber-200">Другой аккаунт</p>
                    <p className="mt-1 text-amber-100/80">
                      Вы вошли как <span className="font-mono">{session.email}</span>, приглашение для{" "}
                      <span className="font-mono">{info.email}</span>.
                    </p>
                    <p className="mt-2 text-xs text-amber-200/70">
                      Выйдите и войдите под приглашённым email или попросите администратора отправить новое приглашение.
                    </p>
                  </div>
                  <Button
                    className="h-11 w-full"
                    variant="secondary"
                    onClick={() => {
                      clearToken();
                      setSession(null);
                      router.push(loginHref);
                    }}
                  >
                    Выйти и войти как {info.email}
                  </Button>
                </>
              ) : (
                <>
                  <p className="text-sm text-slate-300">
                    Войдите как <span className="font-medium text-white">{info.email}</span>, чтобы принять приглашение.
                  </p>
                  <Button className="h-11 w-full" variant="secondary" asChild>
                    <Link href={loginHref}>Войти как {info.email}</Link>
                  </Button>
                </>
              )}
            </div>
          ) : (
            <div className="mt-8 space-y-4">
              <p className="text-sm font-medium text-white">Создайте аккаунт, чтобы присоединиться к {info.workspace_name}</p>
              <div className="space-y-2">
                <Label htmlFor="full_name" className="text-slate-300">
                  Имя
                </Label>
                <Input
                  id="full_name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="border-white/10 bg-slate-950/50"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password" className="text-slate-300">
                  Пароль (мин. 8 символов)
                </Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                  className="border-white/10 bg-slate-950/50"
                />
              </div>
              <Button
                className="h-11 w-full bg-indigo-600 text-white hover:bg-indigo-500"
                disabled={submitting || password.length < 8}
                onClick={() => void acceptNew()}
              >
                {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Создать аккаунт и войти
              </Button>
              <p className="text-center text-xs text-slate-500">
                Уже есть аккаунт?{" "}
                <Link href={loginHref} className="font-medium text-indigo-400 underline-offset-4 hover:underline">
                  Войдите как {info.email}
                </Link>
              </p>
            </div>
          )}
        </div>

        <p className="mt-8 text-center text-xs text-slate-500">
          <Link href="/login" className="underline-offset-4 hover:text-slate-400 hover:underline">
            Страница входа
          </Link>
        </p>
      </div>
    </div>
  );
}
