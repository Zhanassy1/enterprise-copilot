# Deployment and operations

## Dev vs production

| Aspect | Local development | Production |
|--------|-------------------|------------|
| Compose files | `docker compose up` (default `docker-compose.yml`) | `docker compose -f docker-compose.yml -f docker-compose.prod.yml` plus secrets |
| Postgres / Redis ports | Often published on host (see `docker-compose.yml` comments) | **Not** published (`docker-compose.prod.yml`); DB/Redis only on Docker network |
| API / frontend ports | Published on host | **Not** published by default; terminate TLS at nginx/traefik and join the Docker network, or use `docker-compose.prod-local-ports.yml` for localhost-only smoke tests |
| Credentials | `backend/.env.docker` committed defaults | Strong `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `SECRET_KEY` via secrets manager or `.env` (never commit) |

Copy [`.env.production.example`](../.env.production.example) to `.env` and fill in values before using the production override.

## Security baseline

- **Never** deploy with default `postgres/postgres` or empty Redis password on an untrusted network.
- **Reverse proxy / client IP**: set `USE_FORWARDED_HEADERS=true` only when the API’s **direct** TCP peer is a trusted proxy (e.g. nginx in the same Docker network). Set `TRUSTED_PROXY_IPS` to that proxy’s IP(s) (comma-separated). Without this, `X-Forwarded-For` from clients must not be trusted for rate limits or audit.
- **HSTS**: with `ENVIRONMENT=production`, set `TRUSTED_HTTPS=true` when TLS terminates at the edge so the API can emit `Strict-Transport-Security` (or rely on `X-Forwarded-Proto=https`).
- **Celery** is configured for JSON-only serialization (`accept_content=["json"]`, `result_accept_content=["json"]`) in [`backend/app/celery_app.py`](../backend/app/celery_app.py). Do not enable pickle.
- **CORS**: set `CORS_ORIGINS` to your real frontend origins.
- **CSRF**: enable `CSRF_PROTECTION_ENABLED` when using cookie-based sessions behind the same site policy as documented in your reverse proxy.
- **Workspace header**: in production, `X-Workspace-Id` is required for workspace-scoped routes (see `require_workspace_header_in_production`). For staging parity, set `REQUIRE_WORKSPACE_HEADER_STRICT=true`.

## Storage modes

- **Local volume** (`STORAGE_BACKEND=local`): default in compose; uploads under `uploads` volume.
- **S3-compatible** (`STORAGE_BACKEND=s3`): set `S3_*` variables; optional local **MinIO** for dev: `docker compose --profile objectstorage up -d`, then point `S3_ENDPOINT_URL` at `http://minio:9000` with appropriate keys and bucket.

## Quotas and plans

Workspace quotas and usage events are documented in code under [`backend/app/services/usage_metering.py`](../backend/app/services/usage_metering.py). Enforcement includes:

- Monthly requests, tokens, upload bytes (per `WorkspaceQuota`)
- Rerank calls and PDF pages processed (global caps via settings; `-1` = unlimited, `0` = disabled)
- Concurrent ingestion jobs per workspace
- Per-workspace rate limiting (see `rate_limit_per_workspace_per_minute`)

## Async ingestion and Celery

- **Worker**: `docker compose` service `worker` runs Celery consumers.
- **Beat** (scheduled jobs, e.g. soft-delete retention): `docker compose --profile beat up -d` starts the `beat` service.
- **Retention**: documents with `deleted_at` older than `document_retention_days_after_soft_delete` are purged by `purge_expired_soft_deleted_documents`.

## Observability

- **Logs**: enable JSON lines for the `app.request` logger with `OBSERVABILITY_JSON_LOGS=true`.
- **Metrics**: `GET /metrics` (Prometheus text) includes HTTP counters and `celery_queue_depth` when Redis is reachable.
- **Sentry**: set `SENTRY_DSN` for API and worker.
- **Runbook**:
  - **503 on `/readyz`**: Postgres down or unreachable — check `db` container and `DATABASE_URL`.
  - **Ingestion failures**: inspect `ingestion_jobs` and `audit` logs; check worker logs and Celery retries.
  - **High `celery_queue_depth`**: scale workers or reduce ingestion concurrency.

## Product surfaces (overview)

- **Workspaces & roles**: `owner` / `admin` / `member` / `viewer`; membership gates access.
- **Billing / usage**: `/api/v1/billing/usage` and ledger endpoints (workspace-scoped).
- **Audit**: `/api/v1/audit/logs` for workspace-scoped security events.

## Admin / ops

- Run migrations: `alembic upgrade head` (API container entrypoint should run this on deploy).
- Backups: snapshot Postgres volume and S3 bucket if using object storage.
- **Antivirus**: optional ClamAV hook in upload path (`scan_uploaded_file_safe`); configure for fail-closed in production if required.
