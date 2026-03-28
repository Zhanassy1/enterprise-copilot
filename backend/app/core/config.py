from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    app_name: str = "enterprise-copilot"
    environment: str = Field(default="local")
    api_v1_prefix: str = "/api/v1"
    # When True and environment is production, every workspace-scoped request must send X-Workspace-Id (no implicit first-workspace fallback).
    require_workspace_header_in_production: bool = Field(default=True)
    # When True, require X-Workspace-Id for workspace routes in any environment (staging parity with prod).
    require_workspace_header_strict: bool = Field(default=False)

    # Security
    secret_key: str = Field(default="dev-secret-change-me")
    production_require_redis_password: bool = Field(default=True)
    use_forwarded_headers: bool = Field(default=False)
    trusted_proxy_ips: str = Field(
        default="127.0.0.1,::1",
        description="Comma-separated IPs allowed to set X-Forwarded-* (used with USE_FORWARDED_HEADERS).",
    )
    trusted_https: bool = Field(default=False, description="If true with ENVIRONMENT=production, emit HSTS (behind TLS terminator).")
    access_token_exp_minutes: int = Field(default=60 * 24)
    refresh_token_exp_days: int = Field(default=14, ge=1, le=365)
    email_verification_token_exp_minutes: int = Field(default=60 * 24, ge=5, le=60 * 24 * 30)
    password_reset_token_exp_minutes: int = Field(default=30, ge=5, le=60 * 24)
    rate_limit_per_user_per_minute: int = Field(default=120, ge=10, le=2000)
    rate_limit_per_ip_per_minute: int = Field(default=240, ge=10, le=5000)
    # Stricter limits for brute-force / abuse-prone endpoints (applied in addition to global IP/user limits).
    rate_limit_auth_per_ip_per_minute: int = Field(default=30, ge=3, le=500)
    rate_limit_upload_per_user_per_minute: int = Field(default=30, ge=3, le=500)
    rate_limit_per_workspace_per_minute: int = Field(default=600, ge=10, le=50000)
    # Sliding-window rate limits (Redis-backed when available).
    rate_limit_auth_ip_window_seconds: int = Field(default=60, ge=1, le=3600)
    rate_limit_auth_ip_limit: int = Field(default=30, ge=1, le=10000)
    rate_limit_auth_email_window_seconds: int = Field(default=3600, ge=60, le=86400)
    rate_limit_auth_email_limit: int = Field(default=50, ge=1, le=100000)
    rate_limit_upload_user_window_seconds: int = Field(default=60, ge=1, le=3600)
    rate_limit_upload_user_limit: int = Field(default=30, ge=1, le=10000)
    rate_limit_search_chat_workspace_window_seconds: int = Field(default=60, ge=1, le=3600)
    rate_limit_search_chat_workspace_limit: int = Field(default=200, ge=1, le=1_000_000)

    # CORS
    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")

    # Database
    database_url: str = Field(default="postgresql+psycopg://postgres:postgres@localhost:5432/enterprise_copilot")

    # Redis (jobs/cache later)
    redis_url: str = Field(default="redis://localhost:6379/0")
    redis_socket_connect_timeout_seconds: float = Field(default=2.0, ge=0.5, le=30.0)
    redis_socket_timeout_seconds: float = Field(default=2.0, ge=0.5, le=30.0)
    celery_broker_url: str | None = Field(default=None)
    celery_result_backend_url: str | None = Field(default=None)
    celery_ingestion_queue: str = Field(default="ingestion")
    celery_task_track_started: bool = Field(default=True)
    celery_worker_prefetch_multiplier: int = Field(default=1, ge=1, le=20)
    celery_task_acks_late: bool = Field(default=True)
    celery_task_always_eager: bool = Field(default=False)
    celery_task_eager_propagates: bool = Field(default=True)

    # Storage (relative paths are resolved against backend/)
    upload_dir: str = Field(default="data/uploads")
    storage_backend: str = Field(default="local")
    s3_endpoint_url: str = Field(default="")
    s3_region: str = Field(default="us-east-1")
    s3_access_key_id: str = Field(default="")
    s3_secret_access_key: str = Field(default="")
    s3_bucket: str = Field(default="")
    s3_prefix: str = Field(default="enterprise-copilot")

    @field_validator("upload_dir", mode="after")
    @classmethod
    def resolve_upload_dir(cls, v: str) -> str:
        p = Path(v)
        if not p.is_absolute():
            p = _BACKEND_ROOT / p
        return str(p.resolve())

    # ML / Embeddings
    embedding_model_name: str = Field(default="BAAI/bge-small-en-v1.5")

    # LLM (OpenAI-compatible)
    llm_api_key: str = Field(default="")
    llm_base_url: str = Field(default="https://api.openai.com/v1")
    llm_model: str = Field(default="gpt-4o-mini")
    llm_max_context_tokens: int = Field(default=6000)
    llm_temperature: float = Field(default=0.2)

    # Precision-first decision thresholds
    answer_threshold: float = Field(default=0.62, ge=0.0, le=1.0)
    clarify_threshold: float = Field(default=0.42, ge=0.0, le=1.0)
    retrieval_min_score: float = Field(default=0.22, ge=0.0, le=1.0)
    retrieval_max_near_duplicate_overlap: float = Field(default=0.90, ge=0.0, le=1.0)
    retrieval_hybrid_enabled: bool = Field(default=True)
    retrieval_rrf_k: int = Field(default=60, ge=1, le=2000)
    retrieval_rrf_weight_dense: float = Field(default=1.0, ge=0.0, le=10.0)
    retrieval_rrf_weight_keyword: float = Field(default=1.0, ge=0.0, le=10.0)
    retrieval_candidate_multiplier: int = Field(default=10, ge=2, le=100)
    retrieval_candidate_floor: int = Field(default=60, ge=10, le=1000)
    reranker_enabled: bool = Field(default=True)
    reranker_model_name: str = Field(default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    reranker_top_n: int = Field(default=30, ge=2, le=200)
    # Monthly caps per workspace (enforced via usage_events; OWASP resource consumption).
    max_upload_bytes_per_file: int = Field(default=25 * 1024 * 1024, ge=1024, le=500 * 1024 * 1024)
    max_pdf_pages_per_upload: int = Field(default=500, ge=1, le=50_000)
    # Use -1 for unlimited; 0 disables the feature (rerank / PDF indexing).
    max_rerank_calls_per_workspace_month: int = Field(default=100_000, ge=-1, le=10_000_000)
    max_pdf_pages_processed_per_workspace_month: int = Field(default=500_000, ge=-1, le=50_000_000)
    max_concurrent_ingestion_jobs_per_workspace: int = Field(default=5, ge=1, le=100)
    # Soft-delete retention before physical purge (storage lifecycle).
    document_retention_days_after_soft_delete: int = Field(default=90, ge=1, le=3650)

    # Async ingestion pipeline
    ingestion_async_enabled: bool = Field(default=False)
    ingestion_worker_poll_seconds: float = Field(default=2.0, ge=0.1, le=60.0)
    ingestion_max_attempts: int = Field(default=5, ge=1, le=50)
    ingestion_retry_backoff_seconds: int = Field(default=5, ge=1, le=300)
    ingestion_retry_backoff_max_seconds: int = Field(default=300, ge=1, le=3600)
    ingestion_task_soft_time_limit_seconds: int = Field(default=300, ge=5, le=7200)
    ingestion_task_time_limit_seconds: int = Field(default=360, ge=10, le=7200)
    ingestion_dead_letter_enabled: bool = Field(default=True)
    observability_metrics_enabled: bool = Field(default=True)
    observability_json_logs: bool = Field(default=False)
    observability_sentry_workspace_tag: bool = Field(default=True)
    sentry_dsn: str = Field(default="")
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from_email: str = Field(default="noreply@enterprise-copilot.local")
    app_base_url: str = Field(default="http://localhost:3000")
    csrf_protection_enabled: bool = Field(default=False)

    @property
    def celery_broker(self) -> str:
        return (self.celery_broker_url or self.redis_url).strip()

    @property
    def celery_result_backend(self) -> str | None:
        value = (self.celery_result_backend_url or "").strip()
        if value:
            return value
        return self.celery_broker


settings = Settings()

