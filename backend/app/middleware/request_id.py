import json
import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.trusted_proxy import get_effective_client_ip
from app.middleware.metrics import record_request_metrics
from app.middleware.security_headers import apply_production_security_headers

logger = logging.getLogger("app.request")


class RequestAccessMiddleware(BaseHTTPMiddleware):
    """Request id, Sentry workspace tag, metrics, security headers, access log."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.state.request_id = request_id

        path = request.url.path
        ip = get_effective_client_ip(
            request,
            use_forwarded_headers=bool(settings.use_forwarded_headers),
            trusted_proxy_ips=settings.trusted_proxy_ips,
        )
        if settings.sentry_dsn:
            try:
                import sentry_sdk

                ws_hdr = (request.headers.get("X-Workspace-Id") or "").strip()
                if ws_hdr:
                    sentry_sdk.set_tag("workspace_id", ws_hdr[:128])
            except Exception as e:
                logger.debug("sentry workspace tag failed: %s", e)

        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        record_request_metrics(request.method, path, response.status_code, elapsed_ms)
        if "X-Request-Id" not in response.headers:
            response.headers["X-Request-Id"] = request_id
        apply_production_security_headers(response)
        logger.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": path,
                    "status_code": response.status_code,
                    "latency_ms": round(elapsed_ms, 2),
                    "client_ip": ip,
                },
                ensure_ascii=False,
            )
        )
        return response
