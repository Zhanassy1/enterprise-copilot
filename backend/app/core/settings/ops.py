from pydantic import BaseModel, Field


class OpsSettings(BaseModel):
    app_name: str = "enterprise-copilot"
    environment: str = Field(default="local")
    api_v1_prefix: str = "/api/v1"
    # When True and environment is production, every workspace-scoped request must send X-Workspace-Id (no implicit first-workspace fallback).
    require_workspace_header_in_production: bool = Field(default=True)

    # Database
    database_url: str = Field(default="postgresql+psycopg://postgres:postgres@localhost:5432/enterprise_copilot")

    # Redis (jobs/cache later)
    redis_url: str = Field(default="redis://localhost:6379/0")
    celery_broker_url: str | None = Field(default=None)
    celery_result_backend_url: str | None = Field(default=None)
    celery_task_track_started: bool = Field(default=True)
    celery_worker_prefetch_multiplier: int = Field(default=1, ge=1, le=20)
    celery_task_acks_late: bool = Field(default=True)
    celery_task_always_eager: bool = Field(default=False)
    celery_task_eager_propagates: bool = Field(default=True)

    observability_metrics_enabled: bool = Field(default=True)
    sentry_dsn: str = Field(default="")
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from_email: str = Field(default="noreply@enterprise-copilot.local")
    # In-memory capture for unit/integration tests only; must stay false in production (startup_checks).
    email_capture_mode: bool = Field(default=False)
    app_base_url: str = Field(default="http://localhost:3000")

    @property
    def celery_broker(self) -> str:
        return (self.celery_broker_url or self.redis_url).strip()

    @property
    def celery_result_backend(self) -> str | None:
        value = (self.celery_result_backend_url or "").strip()
        if value:
            return value
        return self.celery_broker
