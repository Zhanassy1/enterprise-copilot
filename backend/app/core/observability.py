"""Logging and metrics helpers."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from app.core.config import settings

_json_logging_configured = False


def configure_json_stdout_logging() -> None:
    global _json_logging_configured
    if not settings.observability_json_logs or _json_logging_configured:
        return

    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            payload: dict[str, Any] = {
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            if hasattr(record, "request_id"):
                payload["request_id"] = getattr(record, "request_id", None)
            if record.exc_info:
                payload["exc_info"] = self.formatException(record.exc_info)
            return json.dumps(payload, ensure_ascii=False)

    req = logging.getLogger("app.request")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    req.addHandler(handler)
    req.setLevel(logging.INFO)
    _json_logging_configured = True


def celery_ingestion_queue_depth() -> int:
    """Best-effort Redis LLEN for the Celery ingestion queue (for /metrics)."""
    try:
        import redis

        r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        q = (settings.celery_ingestion_queue or "ingestion").strip() or "ingestion"
        return int(r.llen(q))
    except Exception:
        return -1
