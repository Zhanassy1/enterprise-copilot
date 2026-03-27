"use client";

import { useState, useCallback, useEffect } from "react";
import {
  api,
  toErrorMessage,
  type DocumentOut,
  type DocumentSummaryOut,
} from "@/lib/api-client";

export function useDocuments() {
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const docs = await api.listDocuments();
      setDocuments(docs);
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const uploadDocument = useCallback(
    async (file: File) => {
      const result = await api.uploadDocument(file);
      await fetchDocuments();
      return result;
    },
    [fetchDocuments]
  );

  const deleteDocument = useCallback(
    async (id: string) => {
      await api.deleteDocument(id);
      setDocuments((prev) => prev.filter((d) => d.id !== id));
    },
    []
  );

  const getSummary = useCallback(
    async (id: string): Promise<DocumentSummaryOut> => {
      return api.getDocumentSummary(id);
    },
    []
  );

  return {
    documents,
    loading,
    error,
    uploadDocument,
    deleteDocument,
    getSummary,
    refresh: fetchDocuments,
  };
}
