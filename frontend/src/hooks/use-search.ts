"use client";

import { useState, useCallback } from "react";
import { toast } from "sonner";
import {
  api,
  toErrorMessage,
  type AnswerStyle,
  type SearchOut,
} from "@/lib/api-client";

export function useSearch() {
  const [result, setResult] = useState<SearchOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(
    async (query: string, topK = 5, answerStyle?: AnswerStyle | null) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.search(query, topK, answerStyle);
      setResult(data);
    } catch (err) {
      const msg = toErrorMessage(err);
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  },
  []);

  const clear = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return { result, loading, error, search, clear };
}
