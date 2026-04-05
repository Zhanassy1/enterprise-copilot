const NAMES: Record<string, string> = {
  free: "Free",
  pro: "Pro",
  team: "Team",
};

const ORDER = ["free", "pro", "team"] as const;

export function normalizePlanSlug(slug: string): string {
  return (slug || "free").toLowerCase().trim();
}

export function planDisplayName(slug: string): string {
  const s = normalizePlanSlug(slug);
  return NAMES[s] ?? s.charAt(0).toUpperCase() + s.slice(1);
}

/** Следующий уровень для upgrade CTA; null если уже team или неизвестно. */
export function nextPublicPlanSlug(current: string): "pro" | "team" | null {
  const s = normalizePlanSlug(current);
  if (s === "free") return "pro";
  if (s === "pro") return "team";
  return null;
}

/** Предыдущий уровень (для копии про downgrade через портал). */
export function prevPublicPlanSlug(current: string): "free" | "pro" | null {
  const s = normalizePlanSlug(current);
  if (s === "team") return "pro";
  if (s === "pro") return "free";
  return null;
}

export function isKnownMarketingPlan(slug: string): boolean {
  const s = normalizePlanSlug(slug);
  return ORDER.includes(s as (typeof ORDER)[number]);
}
