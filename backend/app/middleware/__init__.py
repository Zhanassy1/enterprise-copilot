from fastapi import FastAPI

from app.middleware.csrf import CSRFMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestAccessMiddleware


def register_middleware(app: FastAPI) -> None:
    """Register HTTP middleware. Last added runs outermost (first on incoming request)."""
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(RequestAccessMiddleware)
