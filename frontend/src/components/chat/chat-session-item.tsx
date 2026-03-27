"use client";

import { cn, formatDateTime } from "@/lib/utils";
import type { ChatSessionOut } from "@/lib/api-client";

interface ChatSessionItemProps {
  session: ChatSessionOut;
  active: boolean;
  onClick: () => void;
}

export function ChatSessionItem({ session, active, onClick }: ChatSessionItemProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex w-full flex-col items-start gap-0.5 rounded-xl px-3 py-2.5 text-left text-sm transition-colors",
        active
          ? "bg-accent text-accent-foreground"
          : "text-muted-foreground hover:bg-accent/50"
      )}
    >
      <span className="line-clamp-1 font-medium">{session.title}</span>
      <span className="text-xs opacity-70">
        {formatDateTime(session.updated_at)}
      </span>
    </button>
  );
}
