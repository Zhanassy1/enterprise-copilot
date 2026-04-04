/** Canonical path for an invite deep link (matches email URLs). */
export function invitePathForToken(token: string): string {
  return `/invite/${encodeURIComponent(token)}`;
}

/**
 * Parse invite plain token from `next`:
 * `/invite/<token>` or legacy `/invite?token=...`.
 */
export function inviteTokenFromNextParam(next: string | null): string | undefined {
  if (!next || !next.startsWith("/")) return undefined;
  const pathOnly = next.split("?")[0] ?? "";
  const seg = pathOnly.match(/^\/invite\/([^/]+)$/);
  if (seg?.[1]) {
    const token = decodeURIComponent(seg[1]);
    return token.length >= 16 ? token : undefined;
  }
  const q = next.includes("?") ? next.slice(next.indexOf("?") + 1) : "";
  const token = new URLSearchParams(q).get("token");
  return token && token.length >= 16 ? token : undefined;
}
