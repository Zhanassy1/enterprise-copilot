import {
  CreditCard,
  FileText,
  ListTree,
  MessageSquare,
  Search,
  Shield,
  ShieldEllipsis,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { workspaceAppHref } from "@/lib/workspace-path";

export interface AppNavItem {
  /** Path after `/w/:slug` (e.g. `/documents`), or full path if `absolute`. */
  segment: string;
  label: string;
  icon: LucideIcon;
  /** Full app path, not scoped under `/w/:slug`. */
  absolute?: boolean;
}

export const appNavItems: AppNavItem[] = [
  { segment: "/documents", label: "Документы", icon: FileText },
  { segment: "/search", label: "Поиск", icon: Search },
  { segment: "/chat", label: "Чат", icon: MessageSquare },
  { segment: "/team", label: "Команда", icon: Users },
  { segment: "/billing", label: "План и лимиты", icon: CreditCard },
  { segment: "/jobs", label: "Очередь обработки", icon: ListTree },
  { segment: "/audit", label: "Аудит", icon: Shield },
  { segment: "/admin", label: "Админ", icon: ShieldEllipsis, absolute: true },
];

export function navItemHref(slug: string | undefined, item: AppNavItem): string {
  if (item.absolute) return item.segment;
  return slug ? workspaceAppHref(slug, item.segment) : item.segment;
}
