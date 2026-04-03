from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.core.redis_ping import ping_redis_url
from app.db.session import engine


def register_health_routes(app: FastAPI, settings: Settings) -> None:
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
        except OperationalError:
            return JSONResponse(
                status_code=503,
                content={"ok": False, "db": False, "detail": "Database unavailable — run Docker: docker compose up -d db"},
            )

        want_redis = (
            settings.environment.lower().strip() == "production" or bool(settings.readiness_include_redis)
        )
        if want_redis:
            try:
                ping_redis_url(settings.redis_url)
            except Exception:
                return JSONResponse(
                    status_code=503,
                    content={"ok": False, "db": True, "redis": False, "detail": "Redis unavailable"},
                )
            return {"ok": True, "db": True, "redis": True}

        return {"ok": True, "db": True}
