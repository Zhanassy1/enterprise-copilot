import { ApiError, toErrorMessage } from "@/lib/api-client";

/** Backend quota / plan limit errors (429 or document cap 403). */
export function isQuotaOrLimitError(err: unknown): boolean {
  if (!(err instanceof ApiError)) return false;
  if (err.status === 429) return true;
  if (err.status === 403) {
    const msg = toErrorMessage(err).toLowerCase();
    return msg.includes("document limit") || msg.includes("limit reached");
  }
  return false;
}

/** Match error strings from `toErrorMessage` when only text is available. */
export function isQuotaErrorMessage(message: string | null | undefined): boolean {
  if (!message) return false;
  const m = message.toLowerCase();
  return (
    m.includes("quota exceeded") ||
    m.includes("monthly request quota") ||
    m.includes("monthly token quota") ||
    m.includes("monthly upload quota") ||
    m.includes("monthly rerank quota") ||
    m.includes("document limit") ||
    m.includes("limit reached for this plan")
  );
}
