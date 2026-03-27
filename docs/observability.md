# Observability Setup

## What is available

- Structured JSON request logs in API middleware.
- Request correlation via `X-Request-Id` response header.
- Prometheus-like metrics endpoint: `/metrics`.
- Optional Sentry error reporting (`SENTRY_DSN`).

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
