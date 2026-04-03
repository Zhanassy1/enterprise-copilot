import logging

from fastapi import FastAPI

from app.bootstrap.api_mounting import build_api_v1_app
from app.bootstrap.error_handlers import register_api_error_handlers, register_root_exception_handler
from app.bootstrap.health import register_health_routes
from app.bootstrap.observability import init_sentry, register_metrics_route
from app.bootstrap.startup import configure_cors, register_http_middleware_stack, run_startup_validations
from app.core.config import settings

logger = logging.getLogger("app.request")


def create_app() -> FastAPI:
    run_startup_validations(settings)
    init_sentry(settings, logger)
    app = FastAPI(title=settings.app_name)
    configure_cors(app, settings)
    register_http_middleware_stack(app)
    api = build_api_v1_app(settings)
    register_api_error_handlers(api)
    app.mount(settings.api_v1_prefix, api)
    register_root_exception_handler(app)
    register_health_routes(app, settings)
    register_metrics_route(app, settings, logger)
    return app


app = create_app()
