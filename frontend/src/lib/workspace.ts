const workspaceKey = "ec_workspace_id";
const workspaceSlugKey = "ec_workspace_slug";

export function getWorkspaceId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(workspaceKey);
}

export function setWorkspaceId(id: string): void {
  localStorage.setItem(workspaceKey, id);
}

export function clearWorkspaceId(): void {
  localStorage.removeItem(workspaceKey);
  localStorage.removeItem(workspaceSlugKey);
}

/** Last selected workspace slug — canonical `/w/:slug/...` links and fast legacy redirects. */
export function getWorkspaceSlug(): string | null {
  if (typeof window === "undefined") return null;
  const s = localStorage.getItem(workspaceSlugKey);
  return s && s.trim() ? s.trim() : null;
}

export function setWorkspaceSlug(slug: string): void {
  if (slug.trim()) localStorage.setItem(workspaceSlugKey, slug.trim());
}

/** Prefer API workspace slug; fall back to last stored slug for client links (avoids flat `/team` hrefs). */
export function resolvedWorkspaceSlug(ws: { slug?: string } | null | undefined): string | null {
  const a = ws?.slug?.trim();
  if (a) return a;
  return getWorkspaceSlug();
}
