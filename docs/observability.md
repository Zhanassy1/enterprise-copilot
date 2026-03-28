# Observability Setup

## What is available

- Structured JSON request logs in API middleware (`event: http_request`, `request_id`, `path`, `status_code`, `latency_ms`, `client_ip`).
- Workspace audit rows for quota denials (`event_type: quota.denied`) when enforcement triggers with an open DB session.
- Request correlation via `X-Request-Id` response header (also echoed on rate-limit and error responses).
- Prometheus-like metrics endpoint: `/metrics` (HTTP counters and latency sums).
- Optional Sentry (`SENTRY_DSN`): when `X-Workspace-Id` is present, the tag `workspace_id` is set on the scope for request-scoped errors.
- In production, baseline security headers are added on responses (`X-Content-Type-Options`, `X-Frame-Options`, etc.); HSTS should be set at the TLS terminator.

## Recommended dashboard panels

- Requests per minute by `path` and `status`.
- p95 latency by `path`.
- 429 rate-limit responses by `ip/user`.
- Ingestion job status counts (`queued/processing/retrying/ready/failed`).
- Search decision mix (`answer/clarify/insufficient_context`).

## Minimal alert ideas

- High 5xx error rate for 5 minutes.
- Ingestion failed jobs above threshold.
- Sudden drop in `ready` ingestion throughput.
