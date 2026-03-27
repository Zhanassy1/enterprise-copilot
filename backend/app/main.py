import json
import logging
import time
import uuid
from collections import defaultdict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.api.routers import auth, chat, documents, search
from app.core.config import settings
from app.core.debug_log import debug_log
from app.db.session import engine
from app.services.rate_limiter import is_rate_limited

logger = logging.getLogger("app.request")
_metrics_counter: dict[str, int] = defaultdict(int)
_metrics_latency_sum_ms: dict[str, float] = defaultdict(float)


def _validate_runtime_configuration() -> None:
    env = settings.environment.lower().strip()
    if env == "production":
        if settings.secret_key == "dev-secret-change-me":
            raise RuntimeError("Production configuration invalid: secret_key must not use default dev value")
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


def create_app() -> FastAPI:
    _validate_runtime_configuration()
    if settings.sentry_dsn:
        try:
            import sentry_sdk

            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                traces_sample_rate=float(settings.sentry_traces_sample_rate),
                environment=settings.environment,
            )
        except Exception:
            logger.exception("Failed to initialize sentry")
    app = FastAPI(title=settings.app_name)

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        # Allow frontend dev hosts like http://192.168.x.x:5173 when Vite runs with --host.
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api = FastAPI(title=settings.app_name, redirect_slashes=False)
    api.include_router(auth.router)
    api.include_router(documents.router)
    api.include_router(search.router)
    api.include_router(chat.router)

    @api.exception_handler(OperationalError)
    async def api_database_unavailable(request: Request, exc: OperationalError):
        # #region agent log
        debug_log(
            hypothesisId="H_db_api",
            location="backend/app/main.py:api_db",
            message="api:operational_error_handler",
            data={"path": request.url.path, "msg": str(exc)},
        )
        # #endregion
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})

    @api.middleware("http")
    async def api_db_timeout_middleware(request: Request, call_next):
        # psycopg / SQLAlchemy иногда отдают обёртки; exception_handler ловит не всегда при mount.
        try:
            return await call_next(request)
        except Exception as exc:
            err: BaseException | None = exc
            for _ in range(8):
                if err is not None and isinstance(err, OperationalError):
                    # #region agent log
                    debug_log(
                        hypothesisId="H_db_mw",
                        location="backend/app/main.py:api_db_mw",
                        message="api:db_error_in_middleware",
                        data={"path": request.url.path, "msg": str(err)},
                    )
                    # #endregion
                    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})
                nxt = getattr(err, "__cause__", None) if err else None
                if nxt is None and err is not None and hasattr(err, "orig"):
                    nxt = err.orig  # type: ignore[attr-defined]
                err = nxt
            raise

    app.mount(settings.api_v1_prefix, api)

    @app.middleware("http")
    async def debug_request_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.state.request_id = request_id
        path = request.url.path
        ip = request.client.host if request.client else "unknown"
        auth = request.headers.get("Authorization") or ""
        user_token = auth[7:27] if auth.startswith("Bearer ") else ""
        if settings.csrf_protection_enabled and request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            cookie_csrf = request.cookies.get("csrftoken") or ""
            header_csrf = request.headers.get("X-CSRF-Token") or ""
            session_cookie = request.cookies.get("session") or ""
            if session_cookie and (not cookie_csrf or not header_csrf or cookie_csrf != header_csrf):
                return JSONResponse(status_code=403, content={"detail": "CSRF validation failed"}, headers={"X-Request-Id": request_id})
        if is_rate_limited("ip", ip, limit=int(settings.rate_limit_per_ip_per_minute)):
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded for IP"}, headers={"X-Request-Id": request_id})
        if user_token and is_rate_limited("user", user_token, limit=int(settings.rate_limit_per_user_per_minute)):
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded for user"}, headers={"X-Request-Id": request_id})

        t0 = time.perf_counter()
        # #region agent log
        debug_log(
            hypothesisId="H_route",
            location="backend/app/main.py:31",
            message="request:start",
            data={"method": request.method, "path": request.url.path},
        )
        # #endregion
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        _metrics_counter[f"requests_total:{request.method}:{path}:{response.status_code}"] += 1
        _metrics_latency_sum_ms[f"latency_ms_sum:{request.method}:{path}"] += elapsed_ms
        response.headers["X-Request-Id"] = request_id
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
        # #region agent log
        debug_log(
            hypothesisId="H_route",
            location="backend/app/main.py:40",
            message="request:end",
            data={"method": request.method, "path": request.url.path, "status": response.status_code},
        )
        # #endregion
        return response

    @app.exception_handler(Exception)
    async def debug_exception_handler(request: Request, exc: Exception):
        # #region agent log
        debug_log(
            hypothesisId="H_unhandled",
            location="backend/app/main.py:52",
            message="request:unhandled_exception",
            data={"method": request.method, "path": request.url.path, "type": type(exc).__name__, "msg": str(exc)},
        )
        # #endregion
        if isinstance(exc, OperationalError):
            return JSONResponse(status_code=503, content={"detail": "Database unavailable"})
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/readyz")
    def readyz() -> dict:
        """Проверка PostgreSQL. Если падает — подними Docker: docker compose up -d db"""
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"ok": True, "db": True}
        except OperationalError as e:
            debug_log(
                hypothesisId="H_readyz",
                location="backend/app/main.py:readyz",
                message="readyz:db_down",
                data={"msg": str(e)},
            )
            return JSONResponse(
                status_code=503,
                content={"ok": False, "db": False, "detail": "Database unavailable — run Docker: docker compose up -d db"},
            )

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        if not settings.observability_metrics_enabled:
            return Response(status_code=404)
        lines: list[str] = []
        for key, value in sorted(_metrics_counter.items()):
            _, method, path, status = key.split(":", 3)
            lines.append(
                f'http_requests_total{{method="{method}",path="{path}",status="{status}"}} {int(value)}'
            )
        for key, value in sorted(_metrics_latency_sum_ms.items()):
            _, method, path = key.split(":", 2)
            lines.append(f'http_request_latency_ms_sum{{method="{method}",path="{path}"}} {float(value):.4f}')
        body = "\n".join(lines) + ("\n" if lines else "")
        return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")

    return app


app = create_app()

