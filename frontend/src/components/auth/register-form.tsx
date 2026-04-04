"use client";

import { useEffect, useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { z } from "zod";
import { registerSchema, type RegisterValues } from "@/lib/validations";
import { useAuth } from "@/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import Link from "next/link";
import { Loader2 } from "lucide-react";
import { siteUrls } from "@/lib/site-urls";
import { invitePathForToken } from "@/lib/invite-nav";

export function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const inviteToken = searchParams.get("invite")?.trim() ?? "";
  const emailFromQuery = searchParams.get("email")?.trim() ?? "";
  const lockInviteEmail =
    inviteToken.length >= 16 && z.string().email().safeParse(emailFromQuery).success;
  const defaultEmail = lockInviteEmail ? emailFromQuery : "";

  const defaults = useMemo(
    () => ({
      full_name: "",
      email: defaultEmail,
      password: "",
      confirm_password: "",
    }),
    [defaultEmail]
  );

  const { register: registerUser, loading } = useAuth();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: defaults,
  });

  useEffect(() => {
    reset(defaults);
  }, [defaults, reset]);

  const onSubmit = async (data: RegisterValues) => {
    const useInvite = inviteToken.length >= 16;
    if (useInvite && data.password.length < 8) {
      toast.error("По приглашению пароль — минимум 8 символов.");
      return;
    }
    const res = await registerUser(data.email, data.password, data.full_name, useInvite ? inviteToken : null);
    if (res.ok) {
      if (useInvite) {
        toast.success("Аккаунт создан, вы вошли в систему.");
        router.replace("/documents");
      } else {
        toast.success("Аккаунт создан. Войдите в систему.");
        router.push("/login");
      }
    } else {
      toast.error(res.error);
    }
  };

  return (
    <Card className="shadow-md">
      <CardHeader>
        <CardTitle className="text-xl">Регистрация</CardTitle>
      </CardHeader>
      <form onSubmit={handleSubmit(onSubmit)}>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="full_name">Имя (необязательно)</Label>
            <Input
              id="full_name"
              placeholder="Иван Иванов"
              {...register("full_name")}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="you@company.com"
              disabled={lockInviteEmail}
              readOnly={lockInviteEmail}
              {...register("email")}
            />
            {errors.email && (
              <p className="text-sm text-destructive">{errors.email.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Пароль</Label>
            <Input
              id="password"
              type="password"
              placeholder="Минимум 6 символов"
              {...register("password")}
            />
            {errors.password && (
              <p className="text-sm text-destructive">{errors.password.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm_password">Подтвердите пароль</Label>
            <Input
              id="confirm_password"
              type="password"
              placeholder="Повторите пароль"
              {...register("confirm_password")}
            />
            {errors.confirm_password && (
              <p className="text-sm text-destructive">
                {errors.confirm_password.message}
              </p>
            )}
          </div>
        </CardContent>
        <CardFooter className="flex-col gap-3">
          <Button type="submit" className="w-full" disabled={loading}>
            {loading && <Loader2 className="animate-spin" />}
            Создать аккаунт
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            Регистрируясь, вы соглашаетесь с{" "}
            <a href={siteUrls.termsOfService} target="_blank" rel="noreferrer" className="underline underline-offset-2">
              условиями
            </a>{" "}
            и{" "}
            <a href={siteUrls.privacyPolicy} target="_blank" rel="noreferrer" className="underline underline-offset-2">
              политикой конфиденциальности
            </a>
            .
          </p>
          <p className="text-sm text-muted-foreground">
            Уже есть аккаунт?{" "}
            <Link
              href={
                inviteToken.length >= 16
                  ? `/login?next=${encodeURIComponent(invitePathForToken(inviteToken))}`
                  : "/login"
              }
              className="font-medium text-foreground underline-offset-4 hover:underline"
            >
              Войти
            </Link>
            {" · "}
            <Link href="/" className="font-medium text-foreground underline-offset-4 hover:underline">
              О продукте
            </Link>
          </p>
        </CardFooter>
      </form>
    </Card>
  );
}
