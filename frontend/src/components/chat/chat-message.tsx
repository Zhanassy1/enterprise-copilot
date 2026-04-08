"use client";

import { cn } from "@/lib/utils";
import { SourcesAccordion } from "./sources-accordion";
import { Bot, User } from "lucide-react";
import type { ChatMessageOut } from "@/lib/api-client";

interface ChatMessageProps {
  message: ChatMessageOut;
  /** Blinking pipe while assistant response is streaming */
  streamCursor?: boolean;
}

export function ChatMessage({ message, streamCursor }: ChatMessageProps) {
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
          {streamCursor ? (
            <span
              className="ml-0.5 inline-block animate-pulse tabular-nums text-foreground/80"
              aria-hidden
            >
              |
            </span>
          ) : null}
        </p>
        {!isUser &&
        (message.details ||
          message.next_step ||
          message.clarifying_question) ? (
          <div className="mt-2 space-y-1 border-t border-border/60 pt-2 text-xs text-muted-foreground">
            {message.details ? (
              <p className="whitespace-pre-wrap">Детали: {message.details}</p>
            ) : null}
            {message.clarifying_question && message.decision !== "answer" ? (
              <p className="whitespace-pre-wrap">
                Уточнение: {message.clarifying_question}
              </p>
            ) : null}
            {message.next_step ? (
              <p className="whitespace-pre-wrap font-medium text-foreground/80">
                Следующий шаг: {message.next_step}
              </p>
            ) : null}
          </div>
        ) : null}
        {!isUser && message.sources && message.sources.length > 0 ? (
          <SourcesAccordion
            sources={message.sources}
            startCollapsed={message.answer_style === "narrative"}
          />
        ) : null}
      </div>
    </div>
  );
}
