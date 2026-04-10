import { getToken, clearToken } from "./auth";
import { getWorkspaceId, getWorkspaceSlug } from "./workspace";

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
    const b = err.body as Record<string, unknown> | string | null;
    if (b && typeof b === "object" && "detail" in b) {
      const d = (b as Record<string, unknown>).detail;
      if (typeof d === "string") return d;
      if (Array.isArray(d)) return d.map((e) => e?.msg ?? String(e)).join("; ");
    }
    if (err.status === 502 || err.status === 503 || err.status === 504) {
      return "API недоступен. Запустите backend на порту 8000 (см. README).";
    }
    // Next proxy к FastAPI при ECONNREFUSED часто отдаёт 500 без JSON detail (тело HTML/текст).
    if (
      err.status === 500 &&
      (b === null ||
        typeof b === "string" ||
        (typeof b === "object" && b !== null && !("detail" in b)))
    ) {
      return "Не удалось связаться с API (часто: backend не запущен на :8000). Проверьте терминал и README.";
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
  if (!headers.has("X-Workspace-Id")) {
    const ws = getWorkspaceId();
    if (ws) headers.set("X-Workspace-Id", ws);
  }

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  const txt = await res.text();
  const body = txt ? safeJson(txt) ?? txt : null;

  if (res.status === 401 && token) {
    clearToken();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.assign("/login");
    }
  }

  if (res.status === 402 && typeof window !== "undefined") {
    const slug = getWorkspaceSlug();
    const billingPath = slug ? `/w/${slug}/billing` : "/billing";
    const onBilling = slug ? window.location.pathname.startsWith(`/w/${slug}/billing`) : false;
    if (onBilling) {
      void import("sonner").then(({ toast }) =>
        toast.error("Операция недоступна до восстановления оплаты или подписки."),
      );
    } else {
      window.location.assign(billingPath);
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
  email_verified?: boolean;
  is_platform_admin?: boolean;
}

export interface MeOut extends UserOut {
  impersonator_id?: string | null;
}

export interface Token {
  access_token: string;
  token_type: string;
  refresh_token?: string | null;
}

export type BillingBannerVariant = "none" | "warning" | "critical";

export type BillingState = "free" | "active" | "trialing" | "grace" | "past_due" | "canceled";

export interface SubscriptionOut {
  plan_slug: string;
  subscription_status: string | null;
  current_period_end: string | null;
  trial_ends_at: string | null;
  grace_ends_at: string | null;
  billing_state: BillingState;
  renewal_at: string | null;
  grace_until: string | null;
  past_due_banner: boolean;
  banner_variant: BillingBannerVariant;
  banner_message: string | null;
}

export interface BillingInvoiceOut {
  id: string;
  number: string | null;
  status: string | null;
  amount_due: number;
  amount_paid: number;
  currency: string;
  created: string;
  hosted_invoice_url?: string | null;
  invoice_pdf?: string | null;
}

export interface BillingUrlOut {
  url: string;
}

export interface InvitationOut {
  id: string;
  email: string;
  role: string;
  status: string;
  expires_at: string | null;
  created_at: string;
  /** Present only when API runs with email capture (tests / dev). */
  plain_token?: string | null;
}

export interface InviteValidateOut {
  workspace_id: string;
  workspace_name: string;
  email: string;
  role: string;
  expires_at: string | null;
  user_exists: boolean;
}

export interface DocumentOut {
  id: string;
  uploaded_by?: string | null;
  filename: string;
  content_type?: string | null;
  status?: string;
  /** Latest ingestion job status when available (queued | processing | …). */
  ingestion_job_status?: string | null;
  error_message?: string | null;
  page_count?: number | null;
  language?: string | null;
  parser_version?: string | null;
  indexed_at?: string | null;
  pdf_kind?: string | null;
  ocr_applied?: boolean | null;
  /** 0–1 share of pages with non-trivial text after extraction (from extraction_meta). */
  extraction_coverage?: number | null;
  created_at: string;
}

export interface WorkspaceOut {
  id: string;
  name: string;
  slug: string;
  role: string;
}

export interface WorkspaceMemberOut {
  user_id: string;
  email: string;
  full_name: string | null;
  role: string;
  joined_at: string;
}

export interface BillingLedgerOut {
  id: string;
  workspace_id: string;
  external_id: string;
  event_type: string;
  amount_cents: number;
  currency: string;
  created_at: string;
}

export interface UsageSummaryOut {
  plan_slug: string;
  monthly_request_limit: number;
  monthly_token_limit: number;
  monthly_upload_bytes_limit: number;
  max_documents: number | null;
  usage_requests_month: number;
  usage_tokens_month: number;
  usage_bytes_month: number;
  document_count: number;
}

export interface IngestionJobOut {
  id: string;
  document_id: string;
  workspace_id: string;
  status: string;
  attempts: number;
  deduplication_key: string;
  celery_task_id?: string | null;
  error_message?: string | null;
  retry_after_seconds?: number | null;
  dead_lettered_at?: string | null;
  created_at: string;
  completed_at?: string | null;
}

export interface AuditLogOut {
  id: string;
  event_type: string;
  user_id?: string | null;
  target_type?: string | null;
  target_id?: string | null;
  metadata_json?: string | null;
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

export type AnswerStyle = "concise" | "narrative";

export interface SearchOut {
  answer?: string | null;
  details?: string | null;
  decision: "answer" | "clarify" | "insufficient_context";
  confidence: number;
  clarifying_question?: string | null;
  next_step?: string | null;
  evidence_collapsed_by_default?: boolean;
  answer_style?: AnswerStyle;
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
  details?: string | null;
  next_step?: string | null;
  clarifying_question?: string | null;
  decision?: "answer" | "clarify" | "insufficient_context" | null;
  answer_style?: AnswerStyle | null;
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
  answer_style?: AnswerStyle;
}

/* ---------- API methods ---------- */

export const api = {
  register: (email: string, password: string, fullName?: string | null, inviteToken?: string | null) =>
    request<UserOut | Token>("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
        full_name: fullName ?? null,
        invite_token: inviteToken ?? null,
      }),
    }),

  login: (email: string, password: string, inviteToken?: string | null) =>
    request<Token>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password, invite_token: inviteToken ?? null }),
    }),

  getMe: () => request<MeOut>("/auth/me"),

  validateInvite: (token: string) =>
    request<InviteValidateOut>(`/invitations/validate?token=${encodeURIComponent(token)}`),

  acceptInvite: (token: string, password?: string | null, fullName?: string | null) =>
    request<Token>("/invitations/accept", {
      method: "POST",
      body: JSON.stringify({
        token,
        password: password ?? null,
        full_name: fullName ?? null,
      }),
    }),

  createWorkspaceInvitation: (workspaceRef: string, email: string, role: string) =>
    request<InvitationOut>(`/workspaces/${workspaceRef}/invitations`, {
      method: "POST",
      body: JSON.stringify({ email, role }),
    }),

  listWorkspaceInvitations: (workspaceRef: string) =>
    request<InvitationOut[]>(`/workspaces/${workspaceRef}/invitations`),

  revokeWorkspaceInvitation: (workspaceRef: string, invitationId: string) =>
    request<{ status: string }>(
      `/workspaces/${workspaceRef}/invitations/${invitationId}/revoke`,
      { method: "POST", body: "{}" }
    ),

  resendWorkspaceInvitation: (workspaceRef: string, invitationId: string) =>
    request<InvitationOut>(
      `/workspaces/${workspaceRef}/invitations/${invitationId}/resend`,
      { method: "POST", body: "{}" }
    ),

  listWorkspaceMembers: (workspaceRef: string) =>
    request<WorkspaceMemberOut[]>(`/workspaces/${workspaceRef}/members`),

  updateWorkspaceMemberRole: (workspaceRef: string, userId: string, role: string) =>
    request<WorkspaceMemberOut>(`/workspaces/${workspaceRef}/members/${userId}`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    }),

  removeWorkspaceMember: (workspaceRef: string, userId: string) =>
    request<{ status: string }>(`/workspaces/${workspaceRef}/members/${userId}`, {
      method: "DELETE",
    }),

  getBillingSubscription: (workspaceId?: string) =>
    request<SubscriptionOut>(
      "/billing/subscription",
      workspaceId ? { headers: { "X-Workspace-Id": workspaceId } } : undefined,
    ),

  getBillingInvoices: () => request<BillingInvoiceOut[]>("/billing/invoices"),

  createBillingPortal: (returnUrl: string) =>
    request<BillingUrlOut>("/billing/portal", {
      method: "POST",
      body: JSON.stringify({ return_url: returnUrl }),
    }),

  createBillingCheckout: (
    successUrl?: string | null,
    cancelUrl?: string | null,
    planSlug: "pro" | "team" = "pro",
  ) =>
    request<BillingUrlOut>("/billing/checkout", {
      method: "POST",
      body: JSON.stringify({
        success_url: successUrl ?? null,
        cancel_url: cancelUrl ?? null,
        plan_slug: planSlug,
      }),
    }),

  adminImpersonate: (userId: string) =>
    request<Token>("/admin/impersonation/start", {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    }),

  adminWorkspaceUsage: (workspaceId: string) =>
    request<UsageSummaryOut>(`/admin/workspaces/${workspaceId}/usage`),

  adminQuotaAdjust: (
    workspaceId: string,
    body: {
      monthly_request_limit?: number | null;
      monthly_token_limit?: number | null;
      extend_grace_days?: number | null;
      plan_slug?: string | null;
    }
  ) =>
    request<{ ok: string }>(`/admin/workspaces/${workspaceId}/quota`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listDocuments: () => request<DocumentOut[]>("/documents"),

  uploadDocument: async (file: File): Promise<DocumentIngestOut> => {
    const token = getToken();
    const ws = getWorkspaceId();
    const fd = new FormData();
    fd.append("file", file);
    const hdr: Record<string, string> = {};
    if (token) hdr.Authorization = `Bearer ${token}`;
    if (ws) hdr["X-Workspace-Id"] = ws;
    const res = await fetch(`${API_BASE}/documents/upload`, {
      method: "POST",
      headers: Object.keys(hdr).length ? hdr : undefined,
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
    request<{ updated: number; mode?: string; task_id?: string | null; message?: string | null }>(
      "/documents/reindex-embeddings",
      {
        method: "POST",
        body: "{}",
      }
    ),

  listWorkspaces: () => request<WorkspaceOut[]>("/workspaces"),

  getBillingUsage: () => request<UsageSummaryOut>("/billing/usage"),

  listBillingLedger: () => request<BillingLedgerOut[]>("/billing/ledger"),

  listAuditLogs: (limit = 50, eventType?: string | null) => {
    const p = new URLSearchParams();
    p.set("limit", String(limit));
    if (eventType?.trim()) p.set("event_type", eventType.trim());
    return request<AuditLogOut[]>(`/audit/logs?${p.toString()}`);
  },

  listAuditLogsAdmin: (limit = 100, eventType?: string | null) => {
    const p = new URLSearchParams();
    p.set("limit", String(limit));
    if (eventType?.trim()) p.set("event_type", eventType.trim());
    return request<AuditLogOut[]>(`/audit/admin/logs?${p.toString()}`);
  },

  listIngestionJobs: (status?: string) => {
    const q = status ? `?status=${encodeURIComponent(status)}` : "";
    return request<IngestionJobOut[]>(`/ingestion/jobs${q}`);
  },

  getDocument: (id: string) => request<DocumentOut>(`/documents/${id}`),

  getDocumentIngestion: (id: string) =>
    request<IngestionJobOut | null>(`/documents/${id}/ingestion`),

  search: (query: string, topK = 5, answerStyle?: AnswerStyle | null) =>
    request<SearchOut>("/search", {
      method: "POST",
      body: JSON.stringify({
        query,
        top_k: topK,
        ...(answerStyle ? { answer_style: answerStyle } : {}),
      }),
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
