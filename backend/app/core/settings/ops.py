from pydantic import BaseModel, Field


class OpsSettings(BaseModel):
    app_name: str = "enterprise-copilot"
    environment: str = Field(default="local")
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = Field(default="postgresql+psycopg://postgres:postgres@localhost:5432/enterprise_copilot")
    # Per-process pool (QueuePool). Total DB connections ≈ (uvicorn/gunicorn workers + celery workers) × (db_pool_size + db_max_overflow) — must stay under Postgres max_connections.
    db_connect_timeout: int = Field(default=10, ge=1, le=120, description="TCP connect timeout in seconds (psycopg)")
    db_pool_size: int = Field(default=5, ge=1, le=100)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    db_pool_recycle: int = Field(default=1800, ge=0, le=86400, description="Seconds before recycling a connection; 0 = SQLAlchemy default (no recycle)")
    db_pool_timeout: int = Field(default=30, ge=1, le=300, description="Seconds to wait for a free connection from the pool")
    db_statement_timeout_ms: int = Field(
        default=0, ge=0, le=3_600_000, description="PostgreSQL statement_timeout; 0 = not set. Use 0 for long migrations/ETL or a separate role."
    )
    db_idle_in_transaction_session_timeout_ms: int = Field(
        default=0, ge=0, le=3_600_000, description="PostgreSQL idle_in_transaction_session_timeout; 0 = not set"
    )
    # Empty: use app_name (psycopg application_name, visible in pg_stat_activity). Override e.g. enterprise-copilot-celery per worker in compose.
    db_application_name: str = Field(default="")
    db_pool_metrics_enabled: bool = Field(default=True, description="Pool/checkout counters; disable in tight unit tests if needed")
    db_checkout_warn_ms: float = Field(
        default=500.0, ge=0.0, description="Log warning if get_db() session acquire exceeds this (ms). 0 = off"
    )

    # Redis (jobs/cache later)
    redis_url: str = Field(default="redis://localhost:6379/0")
    celery_broker_url: str | None = Field(default=None)
    celery_result_backend_url: str | None = Field(default=None)
    celery_task_track_started: bool = Field(default=True)
    celery_worker_prefetch_multiplier: int = Field(default=1, ge=1, le=20)
    celery_task_acks_late: bool = Field(default=True)
    celery_task_always_eager: bool = Field(default=False)
    celery_task_eager_propagates: bool = Field(default=True)

    # When True, /readyz pings Redis in addition to DB (also automatic when ENVIRONMENT=production).
    readiness_include_redis: bool = Field(default=False)

    observability_metrics_enabled: bool = Field(default=True)
    sentry_dsn: str = Field(default="")
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from_email: str = Field(default="noreply@enterprise-copilot.local")
    # Optional: SendGrid Web API (v3). When set, outbound mail uses HTTPS instead of SMTP (see .env.example).
    sendgrid_api_key: str = Field(default="")
    # In-memory capture for unit/integration tests only; must stay false in production (startup_checks).
    email_capture_mode: bool = Field(default=False)
    app_base_url: str = Field(default="http://localhost:3000")

    # Stripe (optional; leave empty for quota-only billing)
    stripe_secret_key: str = Field(default="")
    stripe_webhook_secret: str = Field(default="")
    stripe_price_id: str = Field(
        default="",
        description="Legacy default Pro recurring price id; used when stripe_price_id_pro is empty",
    )
    stripe_price_id_pro: str = Field(
        default="",
        description="Pro Stripe Price id (falls back to stripe_price_id)",
    )
    stripe_price_id_team: str = Field(default="", description="Team Stripe Price id for Checkout / plan mapping")
    billing_grace_period_days: int = Field(default=3, ge=1, le=30)

    # Comma-separated emails treated as platform admins (in addition to users.is_platform_admin)
    platform_admin_emails: str = Field(default="")

    @property
    def celery_broker(self) -> str:
        return (self.celery_broker_url or self.redis_url).strip()

    @property
    def celery_result_backend(self) -> str | None:
        value = (self.celery_result_backend_url or "").strip()
        if value:
            return value
        return self.celery_broker
