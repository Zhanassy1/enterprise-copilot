import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if settings.csrf_protection_enabled and request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            cookie_csrf = request.cookies.get("csrftoken") or ""
            header_csrf = request.headers.get("X-CSRF-Token") or ""
            session_cookie = request.cookies.get("session") or ""
            if session_cookie and (not cookie_csrf or not header_csrf or cookie_csrf != header_csrf):
                request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF validation failed"},
                    headers={"X-Request-Id": request_id},
                )
        return await call_next(request)
