"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { getWorkspaceSlug } from "@/lib/workspace";
import { pathnameToWorkspaceSubpath, workspaceAppHref } from "@/lib/workspace-path";

/** Redirect flat `(app)/…` routes to `/w/:slug/…` using stored slug first, then loaded workspace. */
export function WorkspaceLegacyRedirect() {
  const router = useRouter();
  const { currentWorkspace, loading } = useWorkspace();

  useEffect(() => {
    if (typeof window === "undefined") return;
    const pathname = window.location.pathname;
    if (/^\/w\/[^/]+/.test(pathname)) return;
    const sub = pathnameToWorkspaceSubpath(pathname);
    const stored = getWorkspaceSlug();
    if (stored) {
      router.replace(workspaceAppHref(stored, sub));
    }
  }, [router]);

  useEffect(() => {
    if (loading) return;
    if (!currentWorkspace?.slug) return;
    if (typeof window === "undefined") return;
    const pathname = window.location.pathname;
    if (/^\/w\/[^/]+/.test(pathname)) return;
    const sub = pathnameToWorkspaceSubpath(pathname);
    router.replace(workspaceAppHref(currentWorkspace.slug, sub));
  }, [loading, currentWorkspace, router]);

  return (
    <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted-foreground">
      Перенаправление…
    </div>
  );
}
