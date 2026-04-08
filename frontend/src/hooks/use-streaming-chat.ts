"use client";

import { useCallback, useEffect, useState } from "react";
import { getToken, clearToken } from "@/lib/auth";
import {
  api,
  ApiError,
  toErrorMessage,
  type AnswerStyle,
  type ChatMessageOut,
  type SearchHit,
} from "@/lib/api-client";

import { toast } from "sonner";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.trim() || "http://localhost:8000/api/v1";

/** Placeholder id for the assistant message while SSE tokens arrive. */
export const STREAMING_CHAT_MESSAGE_ID = "__streaming__";

function parseSseBlocks(buffer: string): { events: string[]; rest: string } {
  const parts = buffer.split(/\r?\n\r?\n/);
  const rest = parts.pop() ?? "";
  return { events: parts, rest };
}

export function useStreamingChat(
  sessionId: string | null,
  workspaceId: string | null
) {
  const [messages, setMessages] = useState<ChatMessageOut[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingMessages, setLoadingMessages] = useState(false);

  const loadMessages = useCallback(async () => {
    if (!sessionId) {
      setMessages([]);
      return;
    }
    setLoadingMessages(true);
    setError(null);
    try {
      const msgs = await api.listChatMessages(sessionId);
      setMessages(msgs);
    } catch (err) {
      const msg = toErrorMessage(err);
      setError(msg);
      toast.error(msg);
    } finally {
      setLoadingMessages(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void loadMessages();
  }, [loadMessages]);

  const sendMessage = useCallback(
    async (message: string, topK = 5, answerStyle?: AnswerStyle | null) => {
      if (!sessionId || !workspaceId) return;
      const trimmed = message.trim();
      if (!trimmed) return;

      setError(null);
      setIsStreaming(true);

      const now = new Date().toISOString();
      const userOptimistic: ChatMessageOut = {
        id: `temp-user-${Date.now()}`,
        session_id: sessionId,
        role: "user",
        content: trimmed,
        sources: [],
        created_at: now,
      };
      const assistantShell: ChatMessageOut = {
        id: STREAMING_CHAT_MESSAGE_ID,
        session_id: sessionId,
        role: "assistant",
        content: "",
        sources: [],
        created_at: now,
      };

      setMessages((prev) => [...prev, userOptimistic, assistantShell]);

      const headers = new Headers();
      headers.set("Content-Type", "application/json");
      headers.set("Accept", "text/event-stream");
      const token = getToken();
      if (token) headers.set("Authorization", `Bearer ${token}`);
      headers.set("X-Workspace-Id", workspaceId);

      let acc = "";
      const sourcesAcc: SearchHit[] = [];

      try {
        const res = await fetch(
          `${API_BASE}/chat/sessions/${sessionId}/messages/stream`,
          {
            method: "POST",
            headers,
            body: JSON.stringify({
              message: trimmed,
              top_k: topK,
              ...(answerStyle ? { answer_style: answerStyle } : {}),
            }),
          }
        );

        if (res.status === 401 && token) {
          clearToken();
          if (
            typeof window !== "undefined" &&
            window.location.pathname !== "/login"
          ) {
            window.location.assign("/login");
          }
        }

        if (!res.ok) {
          const txt = await res.text();
          let body: unknown = txt;
          try {
            body = txt ? JSON.parse(txt) : null;
          } catch {
            /* plain text */
          }
          throw new ApiError(`HTTP ${res.status}`, res.status, body);
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error("Поток ответа недоступен");

        const decoder = new TextDecoder();
        let buf = "";

        const processEventBlock = (block: string) => {
          for (const line of block.split(/\r?\n/)) {
            const t = line.trim();
            if (!t.startsWith("data:")) continue;
            const raw = t.slice(5).trim();
            if (!raw) continue;
            let ev: { type?: string; content?: unknown };
            try {
              ev = JSON.parse(raw) as { type?: string; content?: unknown };
            } catch {
              continue;
            }
            const typ = ev.type;
            if (typ === "token") {
              acc += String(ev.content ?? "");
              const slice = acc;
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === STREAMING_CHAT_MESSAGE_ID
                    ? { ...m, content: slice }
                    : m
                )
              );
            } else if (typ === "source") {
              const c = ev.content;
              if (c && typeof c === "object") {
                sourcesAcc.push(c as SearchHit);
                const snap = [...sourcesAcc];
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === STREAMING_CHAT_MESSAGE_ID
                      ? { ...m, sources: snap }
                      : m
                  )
                );
              }
            } else if (typ === "error") {
              throw new Error(String(ev.content ?? "Ошибка потока чата"));
            }
          }
        };

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const { events, rest } = parseSseBlocks(buf);
          buf = rest;
          for (const block of events) {
            processEventBlock(block);
          }
        }
        if (buf.trim()) {
          processEventBlock(buf);
        }

        const synced = await api.listChatMessages(sessionId);
        setMessages(synced);
      } catch (err) {
        const msg = toErrorMessage(err);
        setError(msg);
        toast.error(msg);
        setMessages((prev) =>
          prev.filter(
            (m) =>
              m.id !== STREAMING_CHAT_MESSAGE_ID &&
              m.id !== userOptimistic.id
          )
        );
      } finally {
        setIsStreaming(false);
      }
    },
    [sessionId, workspaceId]
  );

  return {
    messages,
    sendMessage,
    isStreaming,
    error,
    loadingMessages,
    loadMessages,
  };
}
