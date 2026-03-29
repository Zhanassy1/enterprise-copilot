"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/hooks/use-auth";
import { WorkspaceSwitcher } from "@/components/layout/workspace-switcher";
import { NavRoleHint } from "@/components/layout/nav-role-hint";
import { appNavItems } from "@/config/app-nav";

interface MobileNavProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MobileNav({ open, onOpenChange }: MobileNavProps) {
  const pathname = usePathname();
  const { logout } = useAuth();

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="left" className="w-72 overflow-y-auto p-0">
        <SheetHeader className="px-6 py-4">
          <SheetTitle className="text-lg font-bold">Enterprise Copilot</SheetTitle>
        </SheetHeader>
        <Separator />
        <div className="px-3 pt-3">
          <WorkspaceSwitcher />
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          <NavRoleHint />
          {appNavItems.map(({ href, label, icon: Icon }) => {
            const active = pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                onClick={() => onOpenChange(false)}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
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
            onClick={() => {
              onOpenChange(false);
              logout();
            }}
          >
            <LogOut className="h-4 w-4" />
            Выйти
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
