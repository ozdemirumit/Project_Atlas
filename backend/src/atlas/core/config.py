from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ATLAS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "project-atlas-api"
    environment: Literal["development", "test", "production"] = "development"
    enable_api_docs: bool = True
    database_url: str | None = None
    database_required: bool = False
    database_probe_timeout_seconds: float = Field(default=2.0, gt=0.0, le=10.0)
    cors_origins: tuple[AnyHttpUrl, ...] = (AnyHttpUrl("http://localhost:5173"),)

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger("atlas")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
