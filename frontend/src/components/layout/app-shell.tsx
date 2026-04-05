"use client";

import { useEffect, useState } from "react";
import { isAuthenticated } from "@/lib/auth";
import { Sidebar } from "@/components/layout/sidebar";
import { TopBar } from "@/components/layout/topbar";
import { MobileNav } from "@/components/layout/mobile-nav";
import { WorkspaceProvider } from "@/components/workspace/workspace-provider";
import { AppErrorBoundary } from "@/components/app-error-boundary";
import { AppShellBanners } from "@/components/layout/app-shell-banners";
import { WorkspaceGettingStarted } from "@/components/workspace/workspace-getting-started";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!isAuthenticated()) {
      const path = `${window.location.pathname}${window.location.search}`;
      const safe = path.startsWith("/") ? path : "/documents";
      // Hard navigation: встроенные превью иногда не завершают client-side router.replace — тогда «Загрузка…» висит бесконечно.
      window.location.assign(`/login?next=${encodeURIComponent(safe)}`);
      return;
    }
    setChecked(true);
  }, []);

  if (!checked) {
    return (
      <div className="flex h-screen items-center justify-center bg-background text-sm text-muted-foreground">
        Загрузка приложения…
      </div>
    );
  }

  return (
    <WorkspaceProvider>
      <div className="flex h-screen overflow-hidden">
        <div className="hidden lg:block">
          <Sidebar />
        </div>
        <MobileNav open={mobileOpen} onOpenChange={setMobileOpen} />
        <div className="flex flex-1 flex-col overflow-hidden">
          <TopBar onMenuClick={() => setMobileOpen(true)} />
          <main className="flex-1 overflow-y-auto">
            <AppShellBanners />
            <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
              <WorkspaceGettingStarted />
              <AppErrorBoundary>{children}</AppErrorBoundary>
            </div>
          </main>
        </div>
      </div>
    </WorkspaceProvider>
  );
}
