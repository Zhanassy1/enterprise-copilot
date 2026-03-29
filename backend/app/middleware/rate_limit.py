import logging
import os
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.trusted_proxy import get_effective_client_ip
from app.db.session import SessionLocal
from app.services.rate_limiter import RateLimitOutcome, consume_rate_limit
from app.services.usage_metering import effective_rate_limits_for_plan, get_or_create_quota

logger = logging.getLogger(__name__)

_ws_plan_cache: dict[str, tuple[str, float]] = {}
_WS_PLAN_TTL = 60.0


def _plan_slug_for_workspace_header(workspace_id_header: str) -> str:
    s = (workspace_id_header or "").strip()
    if not s:
        return "free"
    try:
        wid = uuid.UUID(s)
    except ValueError:
        return "free"
    now = time.time()
    k = str(wid)
    hit = _ws_plan_cache.get(k)
    if hit and now - hit[1] < _WS_PLAN_TTL:
        return hit[0]

    db = SessionLocal()
    try:
        q = get_or_create_quota(db, wid)
        slug = (q.plan_slug or "free").lower()
    except Exception as e:
        logger.warning("plan slug lookup failed for workspace %s, defaulting free: %s", k, e)
        slug = "free"
    finally:
        db.close()
    _ws_plan_cache[k] = (slug, now)
    return slug


def _json_429(detail: str, request_id: str, outcome: RateLimitOutcome) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": detail},
        headers={
            "X-Request-Id": request_id,
            "Retry-After": str(outcome.retry_after),
            "X-RateLimit-Limit": str(outcome.limit),
            "X-RateLimit-Remaining": str(outcome.remaining),
        },
    )


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method_u = request.method.upper()
        ip = get_effective_client_ip(
            request,
            use_forwarded_headers=bool(settings.use_forwarded_headers),
            trusted_proxy_ips=settings.trusted_proxy_ips,
        )
        ws_hdr = (request.headers.get("X-Workspace-Id") or "").strip()
        rl = effective_rate_limits_for_plan(_plan_slug_for_workspace_header(ws_hdr))
        auth = request.headers.get("Authorization") or ""
        user_token = auth[7:27] if auth.startswith("Bearer ") else ""

        request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())

        _skip_rl_for_integration = os.environ.get("RUN_INTEGRATION_TESTS") == "1"
        if not _skip_rl_for_integration:
            if method_u == "POST" and path in {
                f"{settings.api_v1_prefix}/auth/login",
                f"{settings.api_v1_prefix}/auth/register",
                f"{settings.api_v1_prefix}/auth/refresh",
            }:
                lim = int(rl["auth_ip"])
                out = consume_rate_limit("auth_ip", ip, limit=lim)
                if out.limited:
                    return _json_429(
                        "Rate limit exceeded for authentication",
                        request_id,
                        out,
                    )
            if method_u == "POST" and path == f"{settings.api_v1_prefix}/documents/upload" and user_token:
                lim = int(rl["upload_user"])
                out = consume_rate_limit("upload_user", user_token, limit=lim)
                if out.limited:
                    return _json_429("Rate limit exceeded for uploads", request_id, out)

            _pfx = settings.api_v1_prefix.rstrip("/")
            if method_u == "POST" and user_token and (
                path == f"{_pfx}/search"
                or ("/chat/sessions/" in path and path.endswith("/messages"))
            ):
                lim = int(rl["rag_user"])
                out = consume_rate_limit("rag_user", user_token, limit=lim)
                if out.limited:
                    return _json_429(
                        "Rate limit exceeded for search/chat (RAG)",
                        request_id,
                        out,
                    )

            lim_ip = int(rl["per_ip"])
            out_ip = consume_rate_limit("ip", ip, limit=lim_ip)
            if out_ip.limited:
                return _json_429("Rate limit exceeded for IP", request_id, out_ip)

            if user_token:
                lim_u = int(rl["per_user"])
                out_u = consume_rate_limit("user", user_token, limit=lim_u)
                if out_u.limited:
                    return _json_429("Rate limit exceeded for user", request_id, out_u)

        return await call_next(request)
