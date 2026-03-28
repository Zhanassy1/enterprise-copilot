# Operations runbook

## API returns 503 / Database unavailable

- Check Postgres connectivity from the API container: `GET /readyz` (expects `db: true`).
- Verify `DATABASE_URL`, network policy, and that migrations ran (`alembic upgrade head`).
- See logs: structured JSON lines with `event: http_request` and `status_code`.

## Redis / Celery

- Worker command should run `celery -A app.celery_app.celery_app worker` with the same `REDIS_URL` / broker as the API.
- If ingestion stays `queued`, confirm the worker is up and listening on the `ingestion` queue.
- Stuck jobs: list `GET /api/v1/ingestion/jobs?status=failed` (workspace scope).

## High 429 rate limits

- Tune `rate_limit_*` in settings or identify abusive IPs/users via `X-Request-Id` + logs.
- Workspace quota: see [quotas.md](quotas.md) and billing usage endpoint.

## Metrics

- `GET /metrics` (when `observability_metrics_enabled`) exposes Prometheus-style counters for HTTP requests and latency sums.
- Optional Sentry: set `SENTRY_DSN`; `workspace_id` tag is attached when `X-Workspace-Id` is sent.

## Ingestion failures

- Terminal failures write `ingestion.failed` audit events and set document status `failed`.
- Check worker logs and antivirus (ClamAV) if enabled; see [observability.md](observability.md).

## TLS / proxy

- Terminate TLS in front of the API; set `TRUSTED_PROXY_IPS` when using `USE_FORWARDED_HEADERS`.
