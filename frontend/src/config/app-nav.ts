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

export interface AppNavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export const appNavItems: AppNavItem[] = [
  { href: "/documents", label: "Документы", icon: FileText },
  { href: "/search", label: "Поиск", icon: Search },
  { href: "/chat", label: "Чат", icon: MessageSquare },
  { href: "/team", label: "Команда", icon: Users },
  { href: "/billing", label: "План и лимиты", icon: CreditCard },
  { href: "/jobs", label: "Очередь обработки", icon: ListTree },
  { href: "/audit", label: "Аудит", icon: Shield },
  { href: "/admin", label: "Админ", icon: ShieldEllipsis },
];
