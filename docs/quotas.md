# Quotas and usage

## Plans

Default plan limits are defined in code (`PLAN_LIMITS` / `PLAN_DOCUMENT_CAP` in `usage_metering`). Each workspace has a `WorkspaceQuota` row; billing may adjust limits per customer.

| Plan | Monthly requests (search + chat + upload count) | Monthly tokens (LLM) | Upload bytes / month | Max documents | Concurrent ingestion jobs | Max PDF pages / document |
|------|-------------------------------------------------|----------------------|----------------------|---------------|----------------------------|---------------------------|
| free | 2,000 | 2M | 512 MiB | 50 | 2 | 150 |
| pro | 50,000 | 20M | 5 GiB | 10,000 | 8 | 2,000 |
| team | 500,000 | 200M | 50 GiB | unlimited | 32 | unlimited |

## What counts as usage

- **Requests**: `search_request`, `chat_message`, `document_upload` events (monthly rolling by UTC calendar month).
- **Tokens**: estimated input + output tokens for search and chat (`llm_tokens`).
- **Upload bytes**: per upload after deduplication (duplicate SHA256 reuses existing document and does not consume a new upload slot).
- **Rerank**: when the cross-encoder reranker is enabled, a `rerank_pass` event is recorded for observability (same search still consumes one request + tokens).

## Enforcement

- `assert_quota` runs before expensive paths (search, chat, upload). Document page count is enforced during indexing against the workspace plan.
- Concurrent async ingestion jobs are capped per plan before enqueueing Celery work.
- Quota violations emit a structured log line `event: quota.violation` (logger `app.usage`) for operators and SIEM routing.

## HTTP rate limits (per plan)

Global limits from settings (`rate_limit_*`) are scaled by **plan** via `effective_rate_limits_for_plan` (free < pro < team). When `X-Workspace-Id` is present, the API resolves the workspace plan (cached ~60s) and applies the scaled limits for IP / user / upload. Monthly usage quotas above remain the hard budget.

## API

- `GET /api/v1/billing/usage` returns plan limits and current month totals for the active workspace.
