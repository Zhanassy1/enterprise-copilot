from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
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
            return {"ok": True, "db": True}
        except OperationalError:
            return JSONResponse(
                status_code=503,
                content={"ok": False, "db": False, "detail": "Database unavailable — run Docker: docker compose up -d db"},
            )
