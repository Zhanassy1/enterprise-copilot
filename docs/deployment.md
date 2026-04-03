# Deployment

**Продуктовый контекст:** Enterprise Copilot — multi-tenant AI-платформа для документов; этот документ описывает, как безопасно выкатывать API, worker и зависимости (Postgres, Redis, S3). Обзор возможностей и лимитов: [README.md](../README.md), [quotas.md](quotas.md).

## Development vs production

| | Dev | Production (primary path) |
|---|-----|---------------------------|
| Compose | `docker compose up` — root `docker-compose.yml` | `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build` |
| DB/Redis ports | Published to host (e.g. 5433, 6380) for tooling | **Not** published; services only on internal network |
| Credentials | Default `postgres:postgres` acceptable locally | Strong `POSTGRES_*`, `REDIS_PASSWORD`, `SECRET_KEY`; validated by `startup_checks` when `ENVIRONMENT=production` |
| Ingestion | Worker + async recommended; optional sync indexing only with `ENVIRONMENT=local` + flags | **Async only** (`INGESTION_ASYNC_ENABLED=1`, `ALLOW_SYNC_INGESTION_FOR_DEV=0`) |

Product-level checklist: [README.md](../README.md) section **Production checklist**.

## Docker Compose (recommended baseline)

- **Development**: `docker compose up --build` — see root `docker-compose.yml` (Postgres/Redis ports published for local dev; default `postgres` / no Redis password — **not** for public exposure).
- **Production-style**: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build` — does **not** publish DB/Redis ports; **overrides** dev database/redis credentials. Required variables (fail at `compose config` if missing):

| Variable | Purpose |
|----------|---------|
| `POSTGRES_USER` | DB superuser name (must match user in `DATABASE_URL`) |
| `POSTGRES_PASSWORD` | DB password (must match `DATABASE_URL`) |
| `DATABASE_URL` | e.g. `postgresql+psycopg://USER:PASS@db:5432/enterprise_copilot` — host **`db`** is the compose service name; must **not** use `postgres:postgres` (backend `startup_checks` rejects it in `ENVIRONMENT=production`) |
| `REDIS_PASSWORD` | Passed to `redis-server --requirepass` |
| `REDIS_URL` | e.g. `redis://:REDIS_PASSWORD@redis:6379/0` — same password as `REDIS_PASSWORD` |
| `SECRET_KEY` | Long random string (`openssl rand -hex 32`) |
| `CORS_ORIGINS` | Trusted browser origins for the SPA (comma-separated); required in production — not inherited from dev defaults |

Optional: `POSTGRES_DB` (default `enterprise_copilot`).

**First deploy** with a new DB volume: empty `pgdata` volume picks up `POSTGRES_*`. If you previously ran dev compose on the same volume, rotate credentials only after `docker compose down -v` or use a dedicated volume name for production.

Copy `.env.production.example` to your orchestration layer and replace placeholders. Never commit real secrets.

### `PRODUCTION_REQUIRE_DATABASE_SSL`, `PRODUCTION_REQUIRE_S3_BACKEND`, `PRODUCTION_REQUIRE_TRUSTED_PROXY_IPS`

These default to **enabled** (`1`) in `Settings`: with `ENVIRONMENT=production`, the API fails fast unless `DATABASE_URL` indicates TLS (e.g. `?sslmode=require`), `STORAGE_BACKEND=s3` with bucket/keys, and `TRUSTED_PROXY_IPS` is non-empty. Set any flag to `0` only for intentional staging or for the reference `docker-compose.prod.yml` overlay (internal Postgres without TLS, no MinIO, no ingress).

CORS in production uses **only** `CORS_ORIGINS` (no private-network `allow_origin_regex`); see [`docs/security.md`](security.md).

Implemented in [`backend/app/core/startup_checks.py`](../backend/app/core/startup_checks.py); tests in [`backend/tests/test_startup_checks.py`](../backend/tests/test_startup_checks.py) and [`backend/tests/test_cors_config.py`](../backend/tests/test_cors_config.py).

### Ingestion: production vs dev

- **Production** (`ENVIRONMENT=production`): `startup_checks` requires `INGESTION_ASYNC_ENABLED=1` and **`ALLOW_SYNC_INGESTION_FOR_DEV=0`** (`backend/app/core/startup_checks.py`). HTTP upload never runs in-process indexing (`backend/app/services/document_ingestion.py`); sync reindex in API is disabled (`backend/app/api/routers/documents.py` `reindex_embeddings`).
- **Dev**: `docker-compose.yml` may use `INGESTION_ASYNC_ENABLED=1` with worker; optional local sync path only when `ENVIRONMENT=local`, `INGESTION_ASYNC_ENABLED=0`, and `ALLOW_SYNC_INGESTION_FOR_DEV=1`.

## TLS

- Run the API behind a reverse proxy that terminates HTTPS. Configure `USE_FORWARDED_HEADERS` and `TRUSTED_PROXY_IPS` so client IP and rate limits work correctly.

### Example: nginx (TLS termination)

```nginx
upstream ec_api {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 443 ssl http2;
    server_name copilot.example.com;

    ssl_certificate     /etc/ssl/certs/fullchain.pem;
    ssl_certificate_key /etc/ssl/private/privkey.pem;

    location / {
        proxy_pass http://ec_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Request-Id $request_id;
    }
}
```

Set `TRUSTED_PROXY_IPS` to the nginx host (or ingress CIDR) and `USE_FORWARDED_HEADERS=1` on the API.

### MinIO (S3-compatible) with `S3_ENDPOINT_URL`

Use the same `STORAGE_BACKEND=s3` as for AWS; point `S3_ENDPOINT_URL` at your MinIO URL (e.g. `https://minio.internal:9000`), set `S3_BUCKET`, and create IAM-like keys in MinIO. Do not commit secrets; inject via env or a secrets manager.

## Migrations

- Run `alembic upgrade head` before or as part of the API container start (see compose `worker` / your entrypoint).

## Further reading

- [security.md](security.md)
- [quotas.md](quotas.md)
- [runbook.md](runbook.md)
- [observability.md](observability.md)
- [storage-lifecycle.md](storage-lifecycle.md)
- [email-testing.md](email-testing.md) (SMTP / capture for verify & reset)
- [testing-database.md](testing-database.md) (CI `SQLALCHEMY_USE_NULLPOOL`)
