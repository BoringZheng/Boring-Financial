from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Boring Financial API"
    app_env: str = "dev"
    api_prefix: str = "/api"
    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_minutes: int = 60 * 24 * 7
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/boring_financial"
    redis_url: str = "redis://localhost:6379/0"
    classification_provider: str = "composite"
    openai_api_base: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    model_timeout_seconds: float = 30.0
    model_connect_timeout_seconds: float = 5.0
    model_max_retries: int = 2
    model_max_output_tokens: int = 80
    import_classification_workers: int = 2
    import_progress_commit_interval: int = 10
    local_model_api_base: str = "http://model-service:8001/v1"
    local_model_api_key: str = "EMPTY"
    local_model_name: str = "Qwen2.5-7B-Instruct"
    low_confidence_threshold: float = 0.75
    storage_dir: str = "./storage"
    task_always_eager: bool = True
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:5173"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def base_dir(self) -> Path:
        return Path(__file__).resolve().parents[3]

    @property
    def repo_root(self) -> Path:
        return self.base_dir.parent

    @property
    def uploads_dir(self) -> Path:
        storage_dir = self.storage_dir.replace("./", "")
        return (self.base_dir / storage_dir / "uploads").resolve()

    @property
    def reports_dir(self) -> Path:
        storage_dir = self.storage_dir.replace("./", "")
        return (self.base_dir / storage_dir / "reports").resolve()

    @property
    def category_map_path(self) -> Path:
        return self.repo_root / "category_map.csv"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
