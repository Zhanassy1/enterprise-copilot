from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings
from app.core.startup_checks import validate_settings
from app.middleware import register_middleware


def run_startup_validations(settings: Settings) -> None:
    validate_settings(settings)


def configure_cors(app: FastAPI, settings: Settings) -> None:
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


def register_http_middleware_stack(app: FastAPI) -> None:
    register_middleware(app)
