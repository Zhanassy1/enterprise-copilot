"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/hooks/use-auth";
import { WorkspaceSwitcher } from "@/components/layout/workspace-switcher";
import { NavRoleHint } from "@/components/layout/nav-role-hint";
import { appNavItems, navItemHref } from "@/config/app-nav";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { workspaceAppHref } from "@/lib/workspace-path";

export function Sidebar() {
  const pathname = usePathname();
  const { logout } = useAuth();
  const { currentWorkspace } = useWorkspace();
  const slug = currentWorkspace?.slug;

  return (
    <aside className="flex h-full w-60 flex-col border-r bg-sidebar">
      <div className="flex h-14 items-center px-6">
        <Link
          href={slug ? workspaceAppHref(slug, "/documents") : "/documents"}
          className="text-lg font-bold tracking-tight"
        >
          Enterprise Copilot
        </Link>
      </div>
      <Separator />
      <div className="px-3 pt-3">
        <WorkspaceSwitcher />
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4">
        <NavRoleHint />
        {appNavItems.map((item) => {
          const { label, icon: Icon } = item;
          const href = navItemHref(slug, item);
          const active = href.startsWith("/w/") ? pathname.startsWith(href) || pathname === href : pathname.startsWith(href);
          return (
            <Link
              key={`${item.segment}-${item.absolute ?? false}`}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <Separator />
      <div className="p-3">
        <Button
          variant="ghost"
          className="w-full justify-start gap-3 text-muted-foreground"
          onClick={logout}
        >
          <LogOut className="h-4 w-4" />
          Выйти
        </Button>
      </div>
    </aside>
  );
}
