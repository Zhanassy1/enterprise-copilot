# Security

**Продуктовый контекст:** политика секретов и доверия к proxy относится ко всему жизненному циклу auth и audit в Enterprise Copilot. См. также [README.md](../README.md) (ограничения production).

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
- Outside production, the API may also allow LAN/Vite dev hosts via a fixed `allow_origin_regex` (private RFC1918 addresses and localhost). In **`ENVIRONMENT=production`** that regex is **disabled**: only entries in `CORS_ORIGINS` apply, and startup requires at least one non-empty origin.

## CSRF

- `CSRF_PROTECTION_ENABLED` is off by default for pure JWT Bearer APIs. Enable when using cookie-based sessions aligned with your frontend.

## Rate limits

- Global per-IP and per-user limits apply in middleware; auth and upload endpoints have stricter buckets; **search/chat (RAG)** use `RATE_LIMIT_RAG_PER_USER_PER_MINUTE` (scaled by plan like other buckets). Tune in `Settings` (`rate_limit_*`).

## Headers

- In `ENVIRONMENT=production`, responses include `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Permissions-Policy`. HSTS is usually set at the edge (TLS terminator).

## Database policy

- Production startup rejects `postgres:postgres@` credentials and `localhost` database hosts. Use a private hostname for your managed database.

## Audit

- Workspace-scoped audit logs: `GET /api/v1/audit/logs` with optional `event_type` (exact match) filter; owner/admin: `GET /api/v1/audit/admin/logs` (больший `limit`, см. роутер).
- **Веб-UI** («Аудит»): показывает журнал только для текущего workspace (`X-Workspace-Id`). Сервер фильтрует **только** по `limit` и точному `event_type`; фильтры по участнику (`user_id`), типу цели (`target_type`), `target_id` и **диапазону дат** применяются **в браузере** среди уже загруженных строк (верхняя плашка в UI объясняет degraded mode). Режим «Расширенный» в UI соответствует `GET /audit/admin/logs` и доступен **owner/admin**; участник и наблюдатель получают 403 при прямом вызове админ-маршрута.
- Продуктовые подписи событий (login failed, quota denied, cross-workspace и т.д.) в UI: `frontend/src/lib/audit-event-labels.ts` — без изменения контракта API.
- Quota denials: structured log `event: quota.violation` plus, when applicable, persisted `quota.denied` in `AuditLog`.
- Auth: successful login `auth.login`; **failed login** `auth.login_failed` (no password in metadata; IP in metadata) — `backend/app/api/routers/auth.py`.
- Cross-workspace: `workspace.access_denied` при попытке доступа к workspace без членства (`deps.py`).
- Удаление документа: `document.deleted`; провал индексации: `ingestion.failed` (см. worker).

## Related

- [hardened-deploy.md](hardened-deploy.md) — hardened vs minimal production profiles  
- [deployment.md](deployment.md) — TLS and production compose  
- [email-testing.md](email-testing.md) — verify/reset flows without production SMTP (capture mode)  
