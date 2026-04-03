from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError


def register_api_error_handlers(api: FastAPI) -> None:
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


def register_root_exception_handler(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def debug_exception_handler(_request: Request, exc: Exception):
        if isinstance(exc, OperationalError):
            return JSONResponse(status_code=503, content={"detail": "Database unavailable"})
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
