/** Workspace-scoped app URLs: `/w/{slug}/…` and API path refs (slug preferred). */

/**
 * Flat app routes under (app)/ that mirror /w/:slug/... — legacy redirects and docs.
 * Keep in sync with page stubs that use WorkspaceLegacyRedirect.
 */
export const LEGACY_WORKSPACE_APP_SUBPATHS = [
  "/documents",
  "/chat",
  "/team",
  "/billing",
  "/billing/success",
  "/jobs",
  "/audit",
  "/search",
] as const;

export function workspaceRefForApi(ws: { id: string; slug?: string } | null | undefined): string {
  if (!ws) return "";
  return (ws.slug && ws.slug.trim()) || ws.id;
}

/**
 * Current path under `/w/:slug` → suffix (e.g. `/documents`). Legacy flat routes map to the same suffix.
 */
export function pathnameToWorkspaceSubpath(pathname: string): string {
  const m = pathname.match(/^\/w\/[^/]+(\/.*)?$/);
  if (m) {
    const rest = m[1];
    if (!rest || rest === "/") return "/documents";
    return rest.startsWith("/") ? rest : `/${rest}`;
  }
  if (pathname === "/" || pathname === "") return "/documents";
  return pathname.startsWith("/") ? pathname : `/${pathname}`;
}

export function workspaceAppHref(slug: string, subpath: string): string {
  const p = subpath.startsWith("/") ? subpath : `/${subpath}`;
  return `/w/${slug}${p}`;
}

/** Absolute URLs for Stripe Checkout return (client must pass these when using `/w/:slug` routes). */
export function billingCheckoutReturnUrls(origin: string, slug: string): { successUrl: string; cancelUrl: string } {
  const base = origin.replace(/\/$/, "");
  const successPath = `${workspaceAppHref(slug, "/billing/success")}?checkout=done&session_id={CHECKOUT_SESSION_ID}`;
  const cancelPath = `${workspaceAppHref(slug, "/billing")}?checkout=cancel`;
  return {
    successUrl: `${base}${successPath}`,
    cancelUrl: `${base}${cancelPath}`,
  };
}
