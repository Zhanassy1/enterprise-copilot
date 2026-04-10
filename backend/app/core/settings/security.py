from typing import Literal

from pydantic import BaseModel, Field


class SecuritySettings(BaseModel):
    secret_key: str = Field(default="dev-secret-change-me")
    secret_key_min_length: int = Field(default=32, ge=16, le=256)
    jwt_issuer: str = Field(default="enterprise-copilot")
    jwt_audience: str = Field(default="api")
    # hardened = recommended production path (TLS DB, S3, trusted proxy policy). minimal = self-hosted reference (explicit opt-outs).
    production_profile: Literal["hardened", "minimal"] = Field(default="hardened")
    # When True and ENVIRONMENT=production, DATABASE_URL must indicate TLS (e.g. sslmode=require).
    production_require_database_ssl: bool = Field(default=True)
    # When True and ENVIRONMENT=production, STORAGE_BACKEND must be s3 (MinIO/S3-first production path).
    production_require_s3_backend: bool = Field(default=True)
    # When True and ENVIRONMENT=production, TRUSTED_PROXY_IPS must be non-empty (API always behind a known LB/ingress).
    production_require_trusted_proxy_ips: bool = Field(default=True)
    # When True and ENVIRONMENT=production, Redis must be reachable for distributed rate limiting (no per-process fallback).
    production_require_redis_rate_limiting: bool = Field(default=True)
    access_token_exp_minutes: int = Field(default=60 * 24)
    refresh_token_exp_days: int = Field(default=14, ge=1, le=365)
    email_verification_token_exp_minutes: int = Field(default=60 * 24, ge=5, le=60 * 24 * 30)
    password_reset_token_exp_minutes: int = Field(default=30, ge=5, le=60 * 24)
    workspace_invitation_exp_hours: int = Field(default=168, ge=1, le=24 * 60)
    rate_limit_per_user_per_minute: int = Field(default=120, ge=10, le=2000)
    rate_limit_per_ip_per_minute: int = Field(default=240, ge=10, le=5000)
    # Stricter limits for brute-force / abuse-prone endpoints (applied in addition to global IP/user limits).
    rate_limit_auth_per_ip_per_minute: int = Field(default=30, ge=3, le=500)
    rate_limit_upload_per_user_per_minute: int = Field(default=30, ge=3, le=500)
    # Search + chat message POSTs (RAG); scaled by plan in middleware like other limits.
    rate_limit_rag_per_user_per_minute: int = Field(default=60, ge=5, le=2000)

    # CORS
    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")

    csrf_protection_enabled: bool = Field(default=False)

    # Reverse proxy: only trust X-Forwarded-* when the direct TCP client is in TRUSTED_PROXY_IPS.
    use_forwarded_headers: bool = Field(default=False)
    trusted_proxy_ips: str = Field(
        default="",
        description="Comma-separated IPs or CIDRs (e.g. 10.0.0.0/8,172.31.0.1) for nginx/ingress.",
    )
