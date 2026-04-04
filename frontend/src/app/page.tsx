"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isAuthenticated } from "@/lib/auth";
import { LandingPage } from "@/components/landing/landing-page";
import { Skeleton } from "@/components/ui/skeleton";

export default function RootPage() {
  const router = useRouter();
  // SSR has no token: render marketing shell immediately (SEO + E2E). Client then redirects if authed.
  const [mode, setMode] = useState<"guest" | "authed">(() =>
    typeof window !== "undefined" && isAuthenticated() ? "authed" : "guest",
  );

  useEffect(() => {
    if (isAuthenticated()) {
      setMode("authed");
      router.replace("/documents");
    } else {
      setMode("guest");
    }
  }, [router]);

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
