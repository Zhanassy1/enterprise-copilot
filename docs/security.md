# Security

## Secrets

- Generate `SECRET_KEY` with a CSPRNG (`openssl rand -hex 32`). Never ship default `dev-secret-change-me` in production.
- Store `DATABASE_URL`, `REDIS_URL`, S3 keys, and `LLM_API_KEY` in a secrets manager or sealed env on the host — not in git.
- Rotate credentials on compromise; password reset revokes all refresh tokens for that user.

## Transport and reverse proxy

- Terminate TLS at your reverse proxy (nginx, Traefik, cloud LB). The API process typically listens on HTTP behind the proxy.
- Set `USE_FORWARDED_HEADERS=1` only together with `TRUSTED_PROXY_IPS`: comma-separated IPs or CIDRs of proxies that append `X-Forwarded-For`. Requests from other clients ignore forwarded headers (spoofing protection).
- Prefer `rediss://` or Redis ACL passwords in production; the app fails fast in `ENVIRONMENT=production` when Redis is unauthenticated on non-localhost hosts.

## CORS

- `CORS_ORIGINS` must list only trusted web origins (scheme + host + port). Wildcards are not used for credentials-heavy setups.

## CSRF

- `CSRF_PROTECTION_ENABLED` is off by default for pure JWT Bearer APIs. Enable when using cookie-based sessions aligned with your frontend.

## Rate limits

- Global per-IP and per-user limits apply in middleware; auth and upload endpoints have stricter buckets. Tune in `Settings` (`rate_limit_*`).

## Headers

- In `ENVIRONMENT=production`, responses include `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Permissions-Policy`. HSTS is usually set at the edge (TLS terminator).

## Database policy

- Production startup rejects `postgres:postgres@` credentials and `localhost` database hosts. Use a private hostname for your managed database.

## Audit

- Workspace-scoped audit logs: `GET /api/v1/audit/logs` with optional `event_type` (exact match) filter.
- Quota denials are logged as structured JSON (`event: quota.violation`, logger `app.usage`) rather than always persisting a row (avoids extra DB connections on the hot path).
