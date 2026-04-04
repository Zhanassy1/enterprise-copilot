"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { workspaceAppHref } from "@/lib/workspace-path";

export default function WorkspaceSlugLayout({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const router = useRouter();
  const slug = typeof params.workspaceSlug === "string" ? params.workspaceSlug : "";
  const { workspaces, loading, syncWorkspaceFromSlug } = useWorkspace();

  useEffect(() => {
    if (loading || !slug) return;
    if (workspaces.length === 0) return;
    const match = workspaces.find((w) => w.slug === slug);
    if (!match) {
      router.replace(workspaceAppHref(workspaces[0]!.slug, "/documents"));
      return;
    }
    syncWorkspaceFromSlug(slug);
  }, [loading, slug, workspaces, router, syncWorkspaceFromSlug]);

  return <>{children}</>;
}
