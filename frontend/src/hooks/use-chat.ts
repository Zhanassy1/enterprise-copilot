"use client";

import { useState, useCallback, useEffect } from "react";
import { toast } from "sonner";
import {
  api,
  toErrorMessage,
  type ChatSessionOut,
} from "@/lib/api-client";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { useStreamingChat } from "@/hooks/use-streaming-chat";

export function useChat() {
  const { currentWorkspace } = useWorkspace();
  const workspaceId = currentWorkspace?.id ?? null;

  const [sessions, setSessions] = useState<ChatSessionOut[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);

  const {
    messages,
    sendMessage: sendStreamingMessage,
    isStreaming,
    error: streamError,
    loadingMessages,
  } = useStreamingChat(activeSessionId, workspaceId);

  const error = sessionError ?? streamError;

  const fetchSessions = useCallback(async () => {
    setLoadingSessions(true);
    try {
      const data = await api.listChatSessions();
      setSessions(data);
    } catch (err) {
      const msg = toErrorMessage(err);
      setSessionError(msg);
      toast.error(msg);
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const selectSession = useCallback((sessionId: string) => {
    setActiveSessionId(sessionId);
    setSessionError(null);
  }, []);

  const createSession = useCallback(async (title?: string) => {
    setSessionError(null);
    try {
      const session = await api.createChatSession(title);
      setSessions((prev) => [session, ...prev]);
      setActiveSessionId(session.id);
      return session;
    } catch (err) {
      const msg = toErrorMessage(err);
      setSessionError(msg);
      toast.error(msg);
      return null;
    }
  }, []);

  const sendMessage = useCallback(
    async (message: string, topK = 5) => {
      if (!activeSessionId) return null;
      await sendStreamingMessage(message, topK);
      try {
        const next = await api.listChatSessions();
        setSessions(next);
      } catch {
        /* список сессий — best-effort */
      }
      return null;
    },
    [activeSessionId, sendStreamingMessage]
  );

  return {
    sessions,
    activeSessionId,
    messages,
    loadingSessions,
    loadingMessages,
    sending: isStreaming,
    isStreaming,
    error,
    selectSession,
    createSession,
    sendMessage,
    refresh: fetchSessions,
  };
}
