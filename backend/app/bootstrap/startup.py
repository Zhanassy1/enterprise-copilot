from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings
from app.core.startup_checks import validate_settings
from app.middleware import register_middleware


def run_startup_validations(settings: Settings) -> None:
    validate_settings(settings)


_DEV_LAN_ORIGIN_REGEX = (
    r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+"
    r"|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?$"
)


def configure_cors(app: FastAPI, settings: Settings) -> None:
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    is_production = settings.environment.lower().strip() == "production"
    cors_kwargs: dict[str, Any] = {
        "allow_origins": origins,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    # Private-network / LAN regex is dev-only; production uses explicit CORS_ORIGINS only (see startup_checks).
    if not is_production:
        cors_kwargs["allow_origin_regex"] = _DEV_LAN_ORIGIN_REGEX
    app.add_middleware(CORSMiddleware, **cors_kwargs)


def register_http_middleware_stack(app: FastAPI) -> None:
    register_middleware(app)
