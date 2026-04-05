"""Fail-fast validation for production and dangerous misconfiguration."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.core.config import Settings
from app.core.redis_ping import ping_redis_url


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


def _database_url_requires_ssl(database_url: str) -> bool:
    low = (database_url or "").lower()
    return "sslmode=require" in low or "ssl=true" in low or "sslmode=verify-full" in low


def _hardened_disallows_opt_out_message(flag: str) -> str:
    return (
        f"Production configuration invalid: PRODUCTION_PROFILE=hardened requires {flag}=1 "
        f"(remove {flag}=0 or set PRODUCTION_PROFILE=minimal for intentional self-hosted opt-outs)"
    )


def validate_production_settings(settings: Settings) -> None:
    """Raise RuntimeError when production configuration is unsafe or incomplete."""
    env = settings.environment.lower().strip()
    if env != "production":
        return

    profile = (settings.production_profile or "hardened").lower().strip()
    if profile == "hardened":
        if not settings.production_require_database_ssl:
            raise RuntimeError(_hardened_disallows_opt_out_message("PRODUCTION_REQUIRE_DATABASE_SSL"))
        if not settings.production_require_s3_backend:
            raise RuntimeError(_hardened_disallows_opt_out_message("PRODUCTION_REQUIRE_S3_BACKEND"))
        if not settings.production_require_trusted_proxy_ips:
            raise RuntimeError(_hardened_disallows_opt_out_message("PRODUCTION_REQUIRE_TRUSTED_PROXY_IPS"))

    sk = (settings.secret_key or "").strip()
    if not sk:
        raise RuntimeError("Production configuration invalid: SECRET_KEY is empty")
    if settings.secret_key == "dev-secret-change-me":
        raise RuntimeError("Production configuration invalid: secret_key must not use default dev value")
    if len(sk) < int(settings.secret_key_min_length):
        raise RuntimeError(
            f"Production configuration invalid: SECRET_KEY must be at least {settings.secret_key_min_length} characters"
        )

    err = _database_url_looks_dev(settings.database_url)
    if err:
        raise RuntimeError(f"Production configuration invalid: {err}")

    cors_origins_list = [o.strip() for o in (settings.cors_origins or "").split(",") if o.strip()]
    if not cors_origins_list:
        raise RuntimeError(
            "Production configuration invalid: CORS_ORIGINS must list at least one trusted browser origin "
            "(scheme + host + port). Private-network regex matching is disabled in production."
        )

    if settings.production_require_trusted_proxy_ips and not (settings.trusted_proxy_ips or "").strip():
        raise RuntimeError(
            "Production configuration invalid: TRUSTED_PROXY_IPS must be set when "
            "PRODUCTION_REQUIRE_TRUSTED_PROXY_IPS=1 (document ingress/LB CIDRs)"
        )

    if settings.production_require_database_ssl and not _database_url_requires_ssl(settings.database_url):
        raise RuntimeError(
            "Production configuration invalid: enable TLS for DATABASE_URL "
            "(e.g. add ?sslmode=require) or set PRODUCTION_REQUIRE_DATABASE_SSL=0 for non-TLS staging only"
        )

    if not settings.ingestion_async_enabled:
        raise RuntimeError(
            "Production configuration invalid: INGESTION_ASYNC_ENABLED must be true in production "
            "(ingestion runs in Celery worker only)"
        )

    if settings.celery_task_always_eager:
        raise RuntimeError(
            "Production configuration invalid: CELERY_TASK_ALWAYS_EAGER must be false in production "
            "(tasks must run on workers, not in the API process)"
        )

    if settings.allow_sync_ingestion_for_dev:
        raise RuntimeError(
            "Production configuration invalid: ALLOW_SYNC_INGESTION_FOR_DEV must be false in production "
            "(sync indexing in API process is dev-only)"
        )

    urls_to_check: list[tuple[str, str]] = [("REDIS_URL", settings.redis_url)]
    broker = (settings.celery_broker_url or "").strip()
    if broker and broker != settings.redis_url.strip():
        urls_to_check.append(("CELERY_BROKER_URL", broker))
    for label, url in urls_to_check:
        rerr = _redis_url_missing_password_in_production(url)
        if rerr:
            raise RuntimeError(f"Production configuration invalid ({label}): {rerr}")

    if settings.production_require_redis_rate_limiting:
        for label, url in urls_to_check:
            try:
                ping_redis_url(url)
            except Exception as e:
                raise RuntimeError(
                    "Production configuration invalid: cannot reach Redis for rate limiting / Celery "
                    f"({label}): {type(e).__name__}"
                ) from e

    sb = settings.storage_backend.lower().strip()
    if settings.production_require_s3_backend and sb != "s3":
        raise RuntimeError(
            "Production configuration invalid: STORAGE_BACKEND must be s3 when PRODUCTION_REQUIRE_S3_BACKEND=1"
        )

    if sb == "s3":
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

    if getattr(settings, "email_capture_mode", False):
        raise RuntimeError(
            "Production configuration invalid: EMAIL_CAPTURE_MODE must be false in production "
            "(in-memory email sink is for tests only)"
        )

    if settings.use_forwarded_headers and not (settings.trusted_proxy_ips or "").strip():
        raise RuntimeError(
            "Production configuration invalid: USE_FORWARDED_HEADERS=1 requires TRUSTED_PROXY_IPS "
            "(comma-separated CIDRs or IPs of your reverse proxies)"
        )


def validate_settings(settings: Settings) -> None:
    """All environments: optional invariants. Production rules are in validate_production_settings."""
    validate_production_settings(settings)
