import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.api.routers import audit, auth, billing, chat, documents, ingestion, search, workspaces
from app.core.config import settings
from app.core.startup_checks import validate_settings
from app.db.session import SessionLocal, engine
from app.middleware import register_middleware
from app.middleware.metrics import get_metrics_state

logger = logging.getLogger("app.request")


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
        except Exception as e:
            logger.exception("Failed to initialize sentry: %s", e)
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

    register_middleware(app)

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
    async def api_database_unavailable(_request: Request, _exc: OperationalError):
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
                    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})
                nxt = getattr(err, "__cause__", None) if err else None
                if nxt is None and err is not None and hasattr(err, "orig"):
                    nxt = err.orig  # type: ignore[attr-defined]
                err = nxt
            raise

    app.mount(settings.api_v1_prefix, api)

    @app.exception_handler(Exception)
    async def debug_exception_handler(_request: Request, exc: Exception):
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
        except OperationalError:
            return JSONResponse(
                status_code=503,
                content={"ok": False, "db": False, "detail": "Database unavailable — run Docker: docker compose up -d db"},
            )

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        if not settings.observability_metrics_enabled:
            return Response(status_code=404)
        _metrics_counter, _metrics_latency_sum_ms = get_metrics_state()
        lines: list[str] = []
        for key, value in sorted(_metrics_counter.items()):
            _, method, path, status = key.split(":", 3)
            lines.append(
                f'http_requests_total{{method="{method}",path="{path}",status="{status}"}} {int(value)}'
            )
        for key, value in sorted(_metrics_latency_sum_ms.items()):
            _, method, path = key.split(":", 2)
            lines.append(f'http_request_latency_ms_sum{{method="{method}",path="{path}"}} {float(value):.4f}')
        try:
            from app.tasks import ingestion as _ing_metrics

            lines.append(f"celery_ingestion_terminal_failures_total {_ing_metrics.ingestion_terminal_failures_total}")
            lines.append(f"celery_ingestion_retries_total {_ing_metrics.ingestion_retries_total}")
        except Exception as e:
            logger.debug("metrics: optional ingestion counters unavailable: %s", e)
        try:
            from sqlalchemy import func, select

            from app.db.session import SessionLocal
            from app.models.document import IngestionJob

            db = SessionLocal()
            try:
                rows = db.execute(
                    select(IngestionJob.status, func.count(IngestionJob.id)).group_by(IngestionJob.status)
                ).all()
                for st, cnt in rows:
                    lines.append(f'ingestion_jobs_total{{status="{st}"}} {int(cnt)}')
            finally:
                db.close()
        except Exception as e:
            logger.debug("metrics: ingestion job counts query failed: %s", e)
        body = "\n".join(lines) + ("\n" if lines else "")
        return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")

    return app


app = create_app()
