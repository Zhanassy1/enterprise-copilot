import json
import logging
import time
import uuid
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.api.routers import audit, auth, billing, chat, documents, ingestion, search, workspaces
from app.core.config import settings
from app.core.debug_log import debug_log
from app.core.startup_checks import validate_settings
from app.core.trusted_proxy import get_effective_client_ip
from app.db.session import engine
from app.services.rate_limiter import is_rate_limited

logger = logging.getLogger("app.request")
_metrics_counter: dict[str, int] = defaultdict(int)
_metrics_latency_sum_ms: dict[str, float] = defaultdict(float)

# #region agent log
_w_main = Path(__file__).resolve()
# Repo root (local): .../enterprise-copilot. In Docker image: parents[2] may be "/" — then use /app (backend mount).
_DBG_LOG = (
    _w_main.parents[1] / "debug-515011.log"
    if str(_w_main.parents[2]) in ("/", "")
    else _w_main.parents[2] / "debug-515011.log"
)


def _dbg515(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    try:
        payload = {
            "sessionId": "515011",
            "timestamp": int(time.time() * 1000),
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
        }
        with _DBG_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


# #endregion


def _apply_production_security_headers(response: Response) -> None:
    if settings.environment.lower().strip() != "production":
        return
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")


def create_app() -> FastAPI:
    validate_settings(settings)
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
    api.include_router(workspaces.router)
    api.include_router(documents.router)
    api.include_router(ingestion.router)
    api.include_router(billing.router)
    api.include_router(audit.router)
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

        def _finish(resp: Response) -> Response:
            if "X-Request-Id" not in resp.headers:
                resp.headers["X-Request-Id"] = request_id
            _apply_production_security_headers(resp)
            return resp
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
            except Exception:
                pass
        auth = request.headers.get("Authorization") or ""
        user_token = auth[7:27] if auth.startswith("Bearer ") else ""
        if settings.csrf_protection_enabled and request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            cookie_csrf = request.cookies.get("csrftoken") or ""
            header_csrf = request.headers.get("X-CSRF-Token") or ""
            session_cookie = request.cookies.get("session") or ""
            if session_cookie and (not cookie_csrf or not header_csrf or cookie_csrf != header_csrf):
                # #region agent log
                _dbg515("H4", "main.py:middleware", "csrf_block", {"path": path})
                # #endregion
                return _finish(JSONResponse(status_code=403, content={"detail": "CSRF validation failed"}, headers={"X-Request-Id": request_id}))
        path = request.url.path
        method_u = request.method.upper()
        if method_u == "POST" and path in {
            f"{settings.api_v1_prefix}/auth/login",
            f"{settings.api_v1_prefix}/auth/register",
            f"{settings.api_v1_prefix}/auth/refresh",
        }:
            if is_rate_limited("auth_ip", ip, limit=int(settings.rate_limit_auth_per_ip_per_minute)):
                # #region agent log
                _dbg515("H4", "main.py:middleware", "rate_limit_auth", {"path": path})
                # #endregion
                return _finish(
                    JSONResponse(
                        status_code=429,
                        content={"detail": "Rate limit exceeded for authentication"},
                        headers={"X-Request-Id": request_id},
                    )
                )
        if method_u == "POST" and path == f"{settings.api_v1_prefix}/documents/upload" and user_token:
            if is_rate_limited("upload_user", user_token, limit=int(settings.rate_limit_upload_per_user_per_minute)):
                # #region agent log
                _dbg515("H4", "main.py:middleware", "rate_limit_upload", {"path": path})
                # #endregion
                return _finish(
                    JSONResponse(
                        status_code=429,
                        content={"detail": "Rate limit exceeded for uploads"},
                        headers={"X-Request-Id": request_id},
                    )
                )

        if is_rate_limited("ip", ip, limit=int(settings.rate_limit_per_ip_per_minute)):
            # #region agent log
            _dbg515("H4", "main.py:middleware", "rate_limit_ip", {"path": path})
            # #endregion
            return _finish(JSONResponse(status_code=429, content={"detail": "Rate limit exceeded for IP"}, headers={"X-Request-Id": request_id}))
        if user_token and is_rate_limited("user", user_token, limit=int(settings.rate_limit_per_user_per_minute)):
            # #region agent log
            _dbg515("H4", "main.py:middleware", "rate_limit_user", {"path": path})
            # #endregion
            return _finish(JSONResponse(status_code=429, content={"detail": "Rate limit exceeded for user"}, headers={"X-Request-Id": request_id}))

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
        # #region agent log
        _api_prefix = settings.api_v1_prefix
        _wrong_api_guess = path.startswith(_api_prefix) is False and path not in ("/healthz", "/readyz", "/favicon.ico", "/metrics") and not path.startswith("/docs") and path != "/openapi.json"
        _dbg515(
            "H3_H4",
            "main.py:middleware",
            "request_complete",
            {
                "path": path,
                "status": response.status_code,
                "method": request.method,
                "maybe_missing_api_prefix": bool(_wrong_api_guess and path != "/"),
            },
        )
        # #endregion
        _metrics_counter[f"requests_total:{request.method}:{path}:{response.status_code}"] += 1
        _metrics_latency_sum_ms[f"latency_ms_sum:{request.method}:{path}"] += elapsed_ms
        response.headers["X-Request-Id"] = request_id
        _finish(response)
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

    @app.get("/")
    def root() -> dict:
        """Чтобы в браузере по http://host:8000/ не было «страница не найдена» без /docs."""
        return {
            "service": settings.app_name,
            "docs": "/docs",
            "openapi": "/openapi.json",
            "healthz": "/healthz",
            "readyz": "/readyz",
            "api": settings.api_v1_prefix,
        }

    @app.get("/healthz")
    def healthz() -> dict:
        # #region agent log
        _dbg515("H1", "main.py:healthz", "healthz_ok", {})
        # #endregion
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
            # #region agent log
            _dbg515("H2", "main.py:readyz", "db_ok", {})
            # #endregion
            return {"ok": True, "db": True}
        except OperationalError as e:
            # #region agent log
            _dbg515("H2", "main.py:readyz", "db_fail", {"msg": str(e)[:200]})
            # #endregion
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

    # #region agent log
    _dbg515(
        "H5",
        "main.py:create_app",
        "create_app_finished",
        {
            "environment": settings.environment,
            "api_v1_prefix": settings.api_v1_prefix,
            "csrf_enabled": bool(settings.csrf_protection_enabled),
        },
    )
    # #endregion
    return app


# #region agent log
try:
    app = create_app()
except Exception as _e:
    _dbg515("H5", "main.py:module", "create_app_failed", {"type": type(_e).__name__, "msg": str(_e)[:500]})
    raise
# #endregion

