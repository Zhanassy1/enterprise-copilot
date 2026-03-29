from fastapi import Response

from app.core.config import settings


def apply_production_security_headers(response: Response) -> None:
    if settings.environment.lower().strip() != "production":
        return
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
