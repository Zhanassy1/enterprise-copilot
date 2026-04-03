from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.settings import (
    IngestionSettings,
    LLMSettings,
    OpsSettings,
    SecuritySettings,
    StorageSettings,
)


class Settings(
    SecuritySettings,
    StorageSettings,
    LLMSettings,
    IngestionSettings,
    OpsSettings,
    BaseSettings,
):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")


settings = Settings()
