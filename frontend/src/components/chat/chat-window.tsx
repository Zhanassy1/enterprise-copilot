"use client";

import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChatMessage } from "./chat-message";
import { ChatInput } from "./chat-input";
import { ChatEmptyState } from "./chat-empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import type { ChatMessageOut } from "@/lib/api-client";
import { STREAMING_CHAT_MESSAGE_ID } from "@/hooks/use-streaming-chat";

interface ChatWindowProps {
  messages: ChatMessageOut[];
  loadingMessages: boolean;
  sending: boolean;
  isStreaming?: boolean;
  hasSession: boolean;
  onSend: (message: string) => void;
  canSend?: boolean;
}

export function ChatWindow({
  messages,
  loadingMessages,
  sending,
  isStreaming = false,
  hasSession,
  onSend,
  canSend = true,
}: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (!hasSession) {
    return <ChatEmptyState />;
  }

  return (
    <div className="flex h-full flex-col">
      <ScrollArea className="flex-1 px-4 py-4">
        {loadingMessages ? (
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-16 rounded-2xl" />
            ))}
          </div>
        ) : messages.length === 0 ? (
          <div className="flex h-full items-center justify-center py-20">
            <p className="text-sm text-muted-foreground">
              Напишите первое сообщение, чтобы начать диалог
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                message={msg}
                streamCursor={
                  isStreaming &&
                  msg.role === "assistant" &&
                  msg.id === STREAMING_CHAT_MESSAGE_ID
                }
              />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </ScrollArea>
      <ChatInput
        onSend={onSend}
        disabled={!canSend || sending || loadingMessages}
        loading={sending || loadingMessages}
        placeholder={
          canSend ? undefined : "Роль «наблюдатель»: отправка сообщений в чат недоступна"
        }
      />
    </div>
  );
}
