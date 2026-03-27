"use client";

import { cn } from "@/lib/utils";
import { SourcesAccordion } from "./sources-accordion";
import { Bot, User } from "lucide-react";
import type { ChatMessageOut } from "@/lib/api-client";

interface ChatMessageProps {
  message: ChatMessageOut;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted"
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-3",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted"
        )}
      >
        <p className="whitespace-pre-wrap text-sm leading-relaxed">
          {message.content}
        </p>
        {!isUser && message.sources && (
          <SourcesAccordion sources={message.sources} />
        )}
      </div>
    </div>
  );
}
