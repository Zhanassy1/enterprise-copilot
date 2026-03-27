"use client";

import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";

interface TopBarProps {
  onMenuClick: () => void;
}

export function TopBar({ onMenuClick }: TopBarProps) {
  return (
    <header className="flex h-14 items-center gap-4 border-b bg-background px-4 lg:hidden">
      <Button variant="ghost" size="icon" onClick={onMenuClick}>
        <Menu className="h-5 w-5" />
        <span className="sr-only">Меню</span>
      </Button>
      <span className="text-lg font-bold tracking-tight">
        Enterprise Copilot
      </span>
    </header>
  );
}
