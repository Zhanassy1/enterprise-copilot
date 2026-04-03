from pathlib import Path

from pydantic import BaseModel, Field, field_validator

_BACKEND_ROOT = Path(__file__).resolve().parents[3]


class StorageSettings(BaseModel):
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
