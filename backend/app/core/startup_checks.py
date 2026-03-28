"""Fail-fast validation for production and dangerous misconfiguration."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.core.config import Settings


def _normalize_jdbc_url(database_url: str) -> str:
    u = database_url.strip()
    for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://"):
        if u.startswith(prefix):
            return "postgresql://" + u.split("://", 1)[1]
    return u


def _database_url_looks_dev(database_url: str) -> str | None:
    """Return error detail if URL is unsuitable for production, else None."""
    u = (database_url or "").strip()
    if not u:
        return "DATABASE_URL is empty"
    low = u.lower()
    # Obvious docker-compose / local defaults
    if re.search(r"postgres:postgres@", low):
        return "DATABASE_URL must not use default postgres:postgres credentials in production"
    parsed = urlparse(_normalize_jdbc_url(u))
    host = (parsed.hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1"):
        return "DATABASE_URL must not point to localhost in production (use a managed DB or private network hostname)"
    return None


def _redis_url_missing_password_in_production(redis_url: str) -> str | None:
    """In production, Redis should not be wide-open (password or TLS)."""
    u = (redis_url or "").strip()
    if not u:
        return "REDIS_URL is empty"
    parsed = urlparse(u)
    if parsed.scheme in ("rediss", "redis"):
        if parsed.scheme == "rediss":
            return None
        host = (parsed.hostname or "").lower()
        if host in ("localhost", "127.0.0.1", "::1", ""):
            return "REDIS_URL must not use unauthenticated localhost Redis in production"
        if parsed.password:
            return None
        return "REDIS_URL must include a password (e.g. redis://:secret@host:6379/0) or use rediss:// in production"
    return None


def validate_production_settings(settings: Settings) -> None:
    """Raise RuntimeError when production configuration is unsafe or incomplete."""
    env = settings.environment.lower().strip()
    if env != "production":
        return

    if settings.secret_key == "dev-secret-change-me":
        raise RuntimeError("Production configuration invalid: secret_key must not use default dev value")

    err = _database_url_looks_dev(settings.database_url)
    if err:
        raise RuntimeError(f"Production configuration invalid: {err}")

    urls_to_check: list[tuple[str, str]] = [("REDIS_URL", settings.redis_url)]
    broker = (settings.celery_broker_url or "").strip()
    if broker and broker != settings.redis_url.strip():
        urls_to_check.append(("CELERY_BROKER_URL", broker))
    for label, url in urls_to_check:
        rerr = _redis_url_missing_password_in_production(url)
        if rerr:
            raise RuntimeError(f"Production configuration invalid ({label}): {rerr}")

    if settings.storage_backend.lower().strip() == "s3":
        required = {
            "s3_bucket": settings.s3_bucket,
            "s3_access_key_id": settings.s3_access_key_id,
            "s3_secret_access_key": settings.s3_secret_access_key,
        }
        missing = [k for k, v in required.items() if not (v or "").strip()]
        if missing:
            raise RuntimeError(f"Production configuration invalid: missing S3 settings: {', '.join(missing)}")

    if settings.llm_api_key and not settings.llm_base_url:
        raise RuntimeError("Production configuration invalid: llm_base_url is required when llm_api_key is set")

    if settings.use_forwarded_headers and not (settings.trusted_proxy_ips or "").strip():
        raise RuntimeError(
            "Production configuration invalid: USE_FORWARDED_HEADERS=1 requires TRUSTED_PROXY_IPS "
            "(comma-separated CIDRs or IPs of your reverse proxies)"
        )


def validate_settings(settings: Settings) -> None:
    """All environments: optional invariants. Production rules are in validate_production_settings."""
    validate_production_settings(settings)
