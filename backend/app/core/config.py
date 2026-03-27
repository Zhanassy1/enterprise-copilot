from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    app_name: str = "enterprise-copilot"
    environment: str = Field(default="local")
    api_v1_prefix: str = "/api/v1"

    # Security
    secret_key: str = Field(default="dev-secret-change-me")
    access_token_exp_minutes: int = Field(default=60 * 24)

    # CORS
    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")

    # Database
    database_url: str = Field(default="postgresql+psycopg://postgres:postgres@localhost:5432/enterprise_copilot")

    # Redis (jobs/cache later)
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Storage (relative paths are resolved against backend/)
    upload_dir: str = Field(default="data/uploads")

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


settings = Settings()

