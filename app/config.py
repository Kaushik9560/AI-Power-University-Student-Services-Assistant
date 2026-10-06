"""Shared application settings. Coordinate before editing this file."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed configuration with local-safe defaults."""

    app_name: str = "University Student Services Assistant"
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///data/students.db"
    chroma_path: str = "data/chroma"
    llm_model: str = "gpt-4.1-mini"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return one settings instance for the process."""

    return Settings()
