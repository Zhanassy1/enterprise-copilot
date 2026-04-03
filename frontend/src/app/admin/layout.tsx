import { AppShell } from "@/components/layout/app-shell";

/** Не кэшировать статически — меньше сбоев RSC/гидрации в Docker. */
export const dynamic = "force-dynamic";

/**
 * /admin вынесен из группы (app), чтобы маршрут стабильно резолвился в Docker/Windows
 * (иногда вложенные пути с route groups не попадали в dev-сервер).
 */
export default function AdminSegmentLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}