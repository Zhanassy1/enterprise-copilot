# Operations runbook

**Продуктовый контекст:** ответы на типичные инциденты для развёртывания Enterprise Copilot (async ingestion, RAG, квоты). Метрики: [observability.md](observability.md).

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
- Plan-scaled HTTP limits use `X-Workspace-Id` + workspace plan (see quotas doc).

## Spike 401 on `/auth/refresh`

- Often expired refresh, reuse after rotation, or revoked session. Check audit for `auth.refresh_reuse_detected`.
- Client should clear tokens and re-login; verify clock skew.

## API returns 400 `X-Workspace-Id header is required`

- Workspace-scoped routes (documents, search, chat, billing scoped by header, etc.) expect a non-empty **`X-Workspace-Id`** (UUID). Call **`GET /api/v1/workspaces`** first, then send the chosen workspace id on subsequent requests. This is intentional: there is no server-side “default workspace” for those routes.

## Queue not moving (ingestion stuck)

- Confirm worker container/process and same `REDIS_URL` / queue name as API.
- Inspect `GET /api/v1/ingestion/jobs?status=queued` and worker logs. Metrics expose `celery_ingestion_retries_total` / `celery_ingestion_terminal_failures_total` on `/metrics` when enabled.

## Metrics

- `GET /metrics` (when `observability_metrics_enabled`) exposes Prometheus-style counters for HTTP requests and latency sums.
- Optional Sentry: set `SENTRY_DSN`; `workspace_id` tag is attached when `X-Workspace-Id` is sent.

## Ingestion failures

- Terminal failures write `ingestion.failed` audit events and set document status `failed`.
- Check worker logs and antivirus (ClamAV) if enabled; see [observability.md](observability.md).
- В приложении страница **«Аудит»** позволяет быстро отфильтровать `ingestion.failed` и `quota.denied` (серверный фильтр по типу + локальные фильтры по времени среди загруженных записей). Расширенный лимит выдачи — под учёткой **owner/admin**.

## Audit / security review (UI)

- Для разборов инцидентов: UI «Аудит» → тип `auth.login_failed`, `workspace.access_denied`, `quota.denied`; при необходимости смотрите таблицу `audit_logs` в БД. Подробности API и ограничений фильтров — [security.md](security.md).

## TLS / proxy

- Terminate TLS in front of the API; set `TRUSTED_PROXY_IPS` when using `USE_FORWARDED_HEADERS`.

## Backup, restore, migrations

- **Postgres**: regular logical dumps (`pg_dump`) or managed backups; test restore to a staging DB quarterly.
- **Object storage**: replicate bucket versioning / cross-region replication per your provider; for MinIO use site replication or external backup of volumes.
- **Alembic**: deploy runs `alembic upgrade head`. For rollback, restore DB from backup taken before the migration, then deploy the previous app image — do not run `downgrade` on production without a DBA-approved plan.
- **Smoke after migrate**: `GET /readyz` (`db: true`), upload a tiny doc, confirm ingestion reaches `ready`.

## Related

- [deployment.md](deployment.md) — production checklist and compose  
- [observability.md](observability.md) — metrics and logs  
