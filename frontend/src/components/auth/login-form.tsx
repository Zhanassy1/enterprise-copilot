"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { loginSchema, type LoginValues } from "@/lib/validations";
import { useAuth } from "@/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import Link from "next/link";
import { Loader2 } from "lucide-react";

export function LoginForm() {
  const router = useRouter();
  const { login, loading } = useAuth();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginValues) => {
    const result = await login(data.email, data.password);
    if (result.ok) {
      toast.success("Вы вошли в систему");
      router.push("/documents");
    } else {
      toast.error(result.error.trim() || "Не удалось войти.");
    }
  };

  return (
    <Card className="shadow-md">
      <CardHeader>
        <CardTitle className="text-xl">Вход в систему</CardTitle>
      </CardHeader>
      <form onSubmit={handleSubmit(onSubmit)}>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="you@company.com"
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
              placeholder="••••••••"
              {...register("password")}
            />
            {errors.password && (
              <p className="text-sm text-destructive">{errors.password.message}</p>
            )}
          </div>
        </CardContent>
        <CardFooter className="flex-col gap-3">
          <Button type="submit" className="w-full" disabled={loading}>
            {loading && <Loader2 className="animate-spin" />}
            Войти
          </Button>
          <p className="text-sm text-muted-foreground">
            Нет аккаунта?{" "}
            <Link href="/register" className="font-medium text-foreground underline-offset-4 hover:underline">
              Зарегистрироваться
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
