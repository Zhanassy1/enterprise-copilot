import { getToken, clearToken } from "./auth";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.trim() || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

export function toErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const b = err.body as Record<string, unknown> | null;
    if (b && typeof b === "object" && "detail" in b) {
      const d = b.detail;
      if (typeof d === "string") return d;
      if (Array.isArray(d)) return d.map((e) => e?.msg ?? String(e)).join("; ");
    }
    return `Ошибка ${err.status}`;
  }
  if (err instanceof Error) return err.message;
  return String(err);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  if (!(init?.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  const txt = await res.text();
  const body = txt ? safeJson(txt) ?? txt : null;

  if (res.status === 401 && token) {
    clearToken();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.assign("/login");
    }
  }

  if (!res.ok) throw new ApiError(`HTTP ${res.status}`, res.status, body);
  return body as T;
}

function safeJson(txt: string) {
  try {
    return JSON.parse(txt);
  } catch {
    return null;
  }
}

/* ---------- Types ---------- */

export interface UserOut {
  id: string;
  email: string;
  full_name?: string | null;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface DocumentOut {
  id: string;
  filename: string;
  content_type?: string | null;
  created_at: string;
}

export interface DocumentIngestOut {
  document: DocumentOut;
  chunks_created: number;
}

export interface DocumentSummaryOut {
  document_id: string;
  summary: string;
}

export interface SearchHit {
  document_id: string;
  chunk_id: string;
  chunk_index: number;
  text: string;
  score: number;
}

export interface SearchOut {
  answer?: string | null;
  details?: string | null;
  decision: "answer" | "clarify" | "insufficient_context";
  confidence: number;
  clarifying_question?: string | null;
  next_step?: string | null;
  evidence_collapsed_by_default?: boolean;
  hits: SearchHit[];
}

export interface ChatSessionOut {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessageOut {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  sources: SearchHit[];
  created_at: string;
}

export interface ChatReplyOut {
  session: ChatSessionOut;
  user_message: ChatMessageOut;
  assistant_message: ChatMessageOut;
  decision: "answer" | "clarify" | "insufficient_context";
  confidence: number;
  details?: string | null;
  clarifying_question?: string | null;
  next_step?: string | null;
  evidence_collapsed_by_default?: boolean;
}

/* ---------- API methods ---------- */

export const api = {
  register: (email: string, password: string, fullName?: string | null) =>
    request<UserOut>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name: fullName ?? null }),
    }),

  login: (email: string, password: string) =>
    request<Token>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  listDocuments: () => request<DocumentOut[]>("/documents"),

  uploadDocument: async (file: File): Promise<DocumentIngestOut> => {
    const token = getToken();
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${API_BASE}/documents/upload`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: fd,
    });
    const txt = await res.text();
    const body = txt ? safeJson(txt) ?? txt : null;
    if (!res.ok) throw new ApiError(`HTTP ${res.status}`, res.status, body);
    return body as DocumentIngestOut;
  },

  deleteDocument: (id: string) =>
    request<{ ok: boolean }>(`/documents/${id}`, { method: "DELETE" }),

  getDocumentSummary: (id: string) =>
    request<DocumentSummaryOut>(`/documents/${id}/summary`),

  reindexEmbeddings: () =>
    request<{ updated: number }>("/documents/reindex-embeddings", {
      method: "POST",
      body: "{}",
    }),

  search: (query: string, topK = 5) =>
    request<SearchOut>("/search", {
      method: "POST",
      body: JSON.stringify({ query, top_k: topK }),
    }),

  listChatSessions: () => request<ChatSessionOut[]>("/chat/sessions"),

  createChatSession: (title?: string) =>
    request<ChatSessionOut>("/chat/sessions", {
      method: "POST",
      body: JSON.stringify({ title: title ?? null }),
    }),

  listChatMessages: (sessionId: string) =>
    request<ChatMessageOut[]>(`/chat/sessions/${sessionId}/messages`),

  sendChatMessage: (sessionId: string, message: string, topK = 5) =>
    request<ChatReplyOut>(`/chat/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ message, top_k: topK }),
    }),
};
