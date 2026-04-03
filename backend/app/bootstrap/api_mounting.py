from fastapi import FastAPI

from app.api.routers import (
    admin,
    audit,
    auth,
    billing,
    billing_webhooks,
    chat,
    documents,
    ingestion,
    invitations,
    search,
    workspaces,
)
from app.core.config import Settings


def build_api_v1_app(settings: Settings) -> FastAPI:
    api = FastAPI(title=settings.app_name, redirect_slashes=False)
    api.include_router(auth.router)
    api.include_router(workspaces.router)
    api.include_router(invitations.router)
    api.include_router(billing_webhooks.router)
    api.include_router(admin.router)
    api.include_router(documents.router)
    api.include_router(ingestion.router)
    api.include_router(billing.router)
    api.include_router(audit.router)
    api.include_router(search.router)
    api.include_router(chat.router)
    return api
