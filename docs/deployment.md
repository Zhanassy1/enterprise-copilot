# Deployment

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

Optional: `POSTGRES_DB` (default `enterprise_copilot`).

**First deploy** with a new DB volume: empty `pgdata` volume picks up `POSTGRES_*`. If you previously ran dev compose on the same volume, rotate credentials only after `docker compose down -v` or use a dedicated volume name for production.

Copy `.env.production.example` to your orchestration layer and replace placeholders. Never commit real secrets.

### `PRODUCTION_REQUIRE_S3_BACKEND`

When `PRODUCTION_REQUIRE_S3_BACKEND=1`, the API refuses to start unless `STORAGE_BACKEND=s3` and S3 settings are present — use for SaaS-style object storage. Omit or `0` for staging with local storage (still use non-dev `DATABASE_URL` / `REDIS_URL` / `SECRET_KEY`).

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
