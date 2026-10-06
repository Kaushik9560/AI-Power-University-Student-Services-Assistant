"""Shared application settings. Coordinate before editing this file."""

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed configuration with local-safe defaults."""

    app_name: str = "University Student Services Assistant"
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///data/students.db"
    chroma_path: str = "data/chroma"
    chroma_collection: str = "university_docs"
    source_register_db: str = "data/source-register.db"
    source_register_path: str = Field("data/source_register.csv", validation_alias="SOURCE_REGISTER")
    retrieval_top_k: int = 8
    retrieval_max_distance: float = 0.75
    chunk_size_chars: int = 900
    chunk_overlap_chars: int = 150
    embedding_provider: str = "minilm"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    ocr_enabled: bool = False
    llm_model: str = "gpt-4.1-mini"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return one settings instance for the process."""

    return Settings()
