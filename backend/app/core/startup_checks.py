"""Fail-fast validation for production deployments (secrets, Redis, proxy policy)."""

from __future__ import annotations

from urllib.parse import urlparse

from app.core.config import settings


def _redis_url_has_password(url: str) -> bool:
    p = urlparse(url.strip())
    if p.password:
        return True
    # redis://:password@host
    netloc = p.netloc or ""
    if "@" in netloc:
        userinfo, _, _ = netloc.rpartition("@")
        if ":" in userinfo:
            part = userinfo.split(":", 1)[-1]
            return bool(part)
    return False


def validate_production_runtime() -> None:
    """Raise RuntimeError if production ENVIRONMENT is configured unsafely."""
    env = settings.environment.lower().strip()
    if env != "production":
        return

    if settings.secret_key == "dev-secret-change-me":
        raise RuntimeError("Production configuration invalid: secret_key must not use default dev value")

    if settings.production_require_redis_password and not _redis_url_has_password(settings.redis_url):
        raise RuntimeError(
            "Production configuration invalid: redis_url must include authentication (password in URL). "
            "Example: redis://:YOUR_PASSWORD@redis:6379/0"
        )

    broker = settings.celery_broker
    if settings.production_require_redis_password and broker and not _redis_url_has_password(broker):
        raise RuntimeError("Production configuration invalid: celery broker URL must include Redis authentication")

    result_backend = settings.celery_result_backend_url or ""
    if result_backend.strip() and settings.production_require_redis_password:
        if not _redis_url_has_password(result_backend):
            raise RuntimeError("Production configuration invalid: celery_result_backend_url must include Redis authentication")

    if settings.use_forwarded_headers and not (settings.trusted_proxy_ips or "").strip():
        raise RuntimeError(
            "Production configuration invalid: USE_FORWARDED_HEADERS=1 requires TRUSTED_PROXY_IPS "
            "(comma-separated IPs that may set X-Forwarded-For)."
        )


def validate_celery_json_policy() -> None:
    """Ensure Celery app rejects non-JSON payloads (defense in depth)."""
    from app.celery_app import celery_app

    conf = celery_app.conf
    if list(getattr(conf, "accept_content", []) or []) != ["json"]:
        raise RuntimeError("Celery configuration invalid: accept_content must be ['json'] only")
    if getattr(conf, "task_serializer", None) != "json":
        raise RuntimeError("Celery configuration invalid: task_serializer must be json")
    if conf.result_serializer != "json":
        raise RuntimeError("Celery configuration invalid: result_serializer must be json")
    rac = getattr(conf, "result_accept_content", None)
    if rac is not None and list(rac) != ["json"]:
        raise RuntimeError("Celery configuration invalid: result_accept_content must be ['json']")
