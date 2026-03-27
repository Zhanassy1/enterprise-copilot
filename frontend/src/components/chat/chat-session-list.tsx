"use client";

import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { ChatSessionItem } from "./chat-session-item";
import type { ChatSessionOut } from "@/lib/api-client";

interface ChatSessionListProps {
  sessions: ChatSessionOut[];
  activeSessionId: string | null;
  loading: boolean;
  onSelect: (id: string) => void;
  onCreate: () => void;
}

export function ChatSessionList({
  sessions,
  activeSessionId,
  loading,
  onSelect,
  onCreate,
}: ChatSessionListProps) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-4 py-3">
        <h2 className="text-sm font-semibold">Чаты</h2>
        <Button variant="ghost" size="icon" onClick={onCreate} title="Новый чат">
          <Plus className="h-4 w-4" />
        </Button>
      </div>
      <Separator />
      <ScrollArea className="flex-1">
        <div className="space-y-1 p-2">
          {loading
            ? Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-14 rounded-xl" />
              ))
            : sessions.map((s) => (
                <ChatSessionItem
                  key={s.id}
                  session={s}
                  active={s.id === activeSessionId}
                  onClick={() => onSelect(s.id)}
                />
              ))}
        </div>
      </ScrollArea>
    </div>
  );
}
