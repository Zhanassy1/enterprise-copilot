"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isAuthenticated } from "@/lib/auth";
import { LandingPage } from "@/components/landing/landing-page";

export default function RootPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"unknown" | "guest" | "authed">("unknown");

  useEffect(() => {
    if (isAuthenticated()) {
      setMode("authed");
      router.replace("/documents");
    } else {
      setMode("guest");
    }
  }, [router]);

  if (mode === "unknown") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-sm text-muted-foreground">
        Загрузка…
      </div>
    );
  }

  if (mode === "authed") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-sm text-muted-foreground">
        Переход в приложение…
      </div>
    );
  }

  return <LandingPage />;
}
