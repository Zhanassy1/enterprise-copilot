"use client";

import { cn } from "@/lib/utils";
import { WorkspaceContextStrip } from "@/components/workspace/workspace-context-strip";
import { WorkspaceMemberLimitedBanner } from "@/components/workspace/workspace-member-limited-banner";
import { WorkspaceViewerBanner } from "@/components/workspace/workspace-viewer-banner";

type MemberLimit = "invite" | "checkout" | null;

type WorkspaceProductContextProps = {
  className?: string;
  /** Что делает страница в контексте workspace (короткая фраза после «Контекст: … —»). */
  area: string;
  /** Текст для плашки наблюдателя; показывается только при роли viewer. */
  viewerDetail: string;
  /** Подсказка для участника (member), если на странице есть админские действия, скрытые в UI. */
  memberLimit?: MemberLimit;
};

/**
 * Единый верх страницы: контекст workspace + роль + ограничения viewer/member.
 */
export function WorkspaceProductContext({
  className = "mt-1",
  area,
  viewerDetail,
  memberLimit = null,
}: WorkspaceProductContextProps) {
  return (
    <div className={cn("space-y-3", className)}>
      <WorkspaceContextStrip area={area} />
      <WorkspaceViewerBanner detail={viewerDetail} />
      {memberLimit ? <WorkspaceMemberLimitedBanner variant={memberLimit} /> : null}
    </div>
  );
}
