"use client";

import { useState, useCallback, useEffect } from "react";
import {
  api,
  toErrorMessage,
  type ChatSessionOut,
  type ChatMessageOut,
} from "@/lib/api-client";

export function useChat() {
  const [sessions, setSessions] = useState<ChatSessionOut[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageOut[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSessions = useCallback(async () => {
    setLoadingSessions(true);
    try {
      const data = await api.listChatSessions();
      setSessions(data);
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const selectSession = useCallback(async (sessionId: string) => {
    setActiveSessionId(sessionId);
    setLoadingMessages(true);
    setError(null);
    try {
      const msgs = await api.listChatMessages(sessionId);
      setMessages(msgs);
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  const createSession = useCallback(
    async (title?: string) => {
      setError(null);
      try {
        const session = await api.createChatSession(title);
        setSessions((prev) => [session, ...prev]);
        setActiveSessionId(session.id);
        setMessages([]);
        return session;
      } catch (err) {
        setError(toErrorMessage(err));
        return null;
      }
    },
    []
  );

  const sendMessage = useCallback(
    async (message: string, topK = 5) => {
      if (!activeSessionId) return null;
      setSending(true);
      setError(null);
      try {
        const reply = await api.sendChatMessage(activeSessionId, message, topK);
        setMessages((prev) => [
          ...prev,
          reply.user_message,
          reply.assistant_message,
        ]);
        setSessions((prev) =>
          prev.map((s) =>
            s.id === reply.session.id ? reply.session : s
          )
        );
        return reply;
      } catch (err) {
        setError(toErrorMessage(err));
        return null;
      } finally {
        setSending(false);
      }
    },
    [activeSessionId]
  );

  return {
    sessions,
    activeSessionId,
    messages,
    loadingSessions,
    loadingMessages,
    sending,
    error,
    selectSession,
    createSession,
    sendMessage,
    refresh: fetchSessions,
  };
}
