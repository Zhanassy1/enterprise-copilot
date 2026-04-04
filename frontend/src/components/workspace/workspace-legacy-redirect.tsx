"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { pathnameToWorkspaceSubpath, workspaceAppHref } from "@/lib/workspace-path";

/** Redirect flat `(app)/…` routes to `/w/:slug/…` once workspace is known. */
export function WorkspaceLegacyRedirect() {
  const router = useRouter();
  const { currentWorkspace, loading } = useWorkspace();

  useEffect(() => {
    if (loading) return;
    if (!currentWorkspace?.slug) return;
    const sub =
      typeof window !== "undefined" ? pathnameToWorkspaceSubpath(window.location.pathname) : "/documents";
    router.replace(workspaceAppHref(currentWorkspace.slug, sub));
  }, [loading, currentWorkspace, router]);

  return (
    <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted-foreground">
      Перенаправление…
    </div>
  );
}
