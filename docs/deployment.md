# Deployment

## Docker Compose (recommended baseline)

- **Development**: `docker compose up --build` — see root `docker-compose.yml` (Postgres/Redis ports published for local dev).
- **Production-style**: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` — removes published DB/Redis ports; set secrets via environment or a secrets manager.

Copy `.env.production.example` to your orchestration layer and replace placeholders. Never commit real secrets.

## TLS

- Run the API behind a reverse proxy that terminates HTTPS. Configure `USE_FORWARDED_HEADERS` and `TRUSTED_PROXY_IPS` so client IP and rate limits work correctly.

## Migrations

- Run `alembic upgrade head` before or as part of the API container start (see compose `worker` / your entrypoint).

## Further reading

- [security.md](security.md)
- [quotas.md](quotas.md)
- [runbook.md](runbook.md)
- [observability.md](observability.md)
- [storage-lifecycle.md](storage-lifecycle.md)
