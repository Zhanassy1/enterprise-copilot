"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isAuthenticated } from "@/lib/auth";
import { LandingPage } from "@/components/landing/landing-page";
import { Skeleton } from "@/components/ui/skeleton";

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
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-4">
        <Skeleton className="h-10 w-48 rounded-lg" />
        <Skeleton className="h-4 w-64 rounded" />
      </div>
    );
  }

  if (mode === "authed") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background px-4">
        <Skeleton className="h-9 w-56 rounded-lg" />
        <p className="text-sm text-muted-foreground">Открываем приложение…</p>
      </div>
    );
  }

  return <LandingPage />;
}
