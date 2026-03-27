from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.api.routers import auth, chat, documents, search
from app.core.config import settings
from app.core.debug_log import debug_log
from app.db.session import engine


def create_app() -> FastAPI:
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
        # #region agent log
        debug_log(
            hypothesisId="H_route",
            location="backend/app/main.py:31",
            message="request:start",
            data={"method": request.method, "path": request.url.path},
        )
        # #endregion
        response = await call_next(request)
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

    return app


app = create_app()

