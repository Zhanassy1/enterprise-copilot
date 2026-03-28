"""OWASP-oriented HTTP response headers for the API."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        env = settings.environment.lower().strip()
        if env == "production":
            proto = (request.headers.get("x-forwarded-proto") or "").lower().strip()
            if settings.trusted_https or proto == "https":
                response.headers.setdefault(
                    "Strict-Transport-Security",
                    "max-age=63072000; includeSubDomains",
                )
        return response
