# Hardened production deployment

**Product context:** same positioning as [README.md](../README.md) — multi-tenant copilot with workspace isolation. This document defines the **recommended production path** (hardened) versus an explicit **minimal** self-hosted profile for reference Docker stacks.

## Profiles

| | **Hardened** (default, recommended) | **Minimal** (self-hosted reference) |
|---|-------------------------------------|-------------------------------------|
| `PRODUCTION_PROFILE` | `hardened` (default in `Settings`) | `minimal` |
| PostgreSQL | Private hostname (not `localhost`), not `postgres:postgres`; **TLS** in `DATABASE_URL` (`sslmode=require` or equivalent) | Internal Docker `db` service without TLS to Postgres — opt-out via `PRODUCTION_REQUIRE_DATABASE_SSL=0` |
| Object storage | **`STORAGE_BACKEND=s3`** with bucket and keys (AWS or S3-compatible / MinIO) | **`local`** or non-S3 allowed only with `PRODUCTION_REQUIRE_S3_BACKEND=0` |
| Trusted proxy | Non-empty **`TRUSTED_PROXY_IPS`** (document LB/ingress CIDRs); **`USE_FORWARDED_HEADERS=1`** when behind a reverse proxy | May use `PRODUCTION_REQUIRE_TRUSTED_PROXY_IPS=0` when nothing terminates TLS in front of the API in that stack |
| Redis | Password in `redis://` or **`rediss://`** on non-localhost hosts | Same — production still requires authenticated Redis when not localhost |
| Secrets | `SECRET_KEY` (long random), DB/Redis/S3 secrets in a vault or sealed env | Same |

Startup validation lives in [`backend/app/core/startup_checks.py`](../backend/app/core/startup_checks.py). With **`PRODUCTION_PROFILE=hardened`**, you **cannot** set `PRODUCTION_REQUIRE_DATABASE_SSL=0`, `PRODUCTION_REQUIRE_S3_BACKEND=0`, or `PRODUCTION_REQUIRE_TRUSTED_PROXY_IPS=0` — the process fails fast with a clear error. Use **`minimal`** only when you intentionally accept those gaps (e.g. internal compose without MinIO or Postgres TLS).

## Canonical env template

Use [`.env.production.example`](../.env.production.example) as the **hardened** template: it sets `PRODUCTION_PROFILE=hardened`, managed DB with TLS, S3, and reverse-proxy fields.

The **minimal** reference for Docker-only stacks is [`docker-compose.prod.yml`](../docker-compose.prod.yml) (sets `PRODUCTION_PROFILE=minimal` and the corresponding `PRODUCTION_REQUIRE_*=0` overrides for API/worker).

## Checklist (hardened)

1. **`ENVIRONMENT=production`** on API and Celery workers (same vars on every process).
2. **`SECRET_KEY`**: CSPRNG (`openssl rand -hex 32`), not `dev-secret-change-me`, length ≥ `SECRET_KEY_MIN_LENGTH`.
3. **`DATABASE_URL`**: non-localhost host, not default `postgres:postgres`, includes TLS for managed DB.
4. **`REDIS_URL`**: password embedded or `rediss://`; reachable from API (startup ping when rate-limit check is on).
5. **`STORAGE_BACKEND=s3`** plus `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` (and `S3_ENDPOINT_URL` for MinIO).
6. **`TRUSTED_PROXY_IPS`**: comma-separated IPs/CIDRs for your LB/ingress; pair with **`USE_FORWARDED_HEADERS=1`** when the API sits behind a proxy.
7. **`CORS_ORIGINS`**: at least one explicit browser origin (no dev-only regex in production).
8. **`INGESTION_ASYNC_ENABLED=1`**, **`ALLOW_SYNC_INGESTION_FOR_DEV=0`**, **`CELERY_TASK_ALWAYS_EAGER=0`**.
9. **`EMAIL_CAPTURE_MODE=0`** (capture mode is test-only).

## CI vs full hardened

Automated compose smoke tests in CI use the **minimal** profile (internal `db`/Redis, no TLS to Postgres in compose) so the stack can start in a runner without external RDS or MinIO. **Hardened** invariants are enforced by unit tests in [`backend/tests/test_startup_checks.py`](../backend/tests/test_startup_checks.py) and by using the hardened template in real deployments.

## Related

- [deployment.md](deployment.md) — compose commands, migrations, TLS nginx example  
- [security.md](security.md) — secrets, proxy headers, CORS  
- [storage-lifecycle.md](storage-lifecycle.md) — object storage behavior  
