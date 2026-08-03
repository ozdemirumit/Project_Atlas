from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal, Self

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
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
    development_identity_enabled: bool = False
    development_subject_id: str = "subject.development.operator"
    development_display_name: str = "Local Operator"
    development_organization_id: str = "organization.development"
    development_role_ids: tuple[str, ...] = ("role.development.operator",)
    local_model_enabled: bool = False
    local_model_base_url: AnyHttpUrl | None = None
    local_model_id: str | None = None
    local_model_reader_token: SecretStr | None = None
    local_model_secret_reference_id: str = "secret.model.local-reader"

    @model_validator(mode="after")
    def enforce_production_security_defaults(self) -> Self:
        if self.environment == "production" and self.development_identity_enabled:
            raise ValueError("development identity cannot be enabled in production")
        if self.environment == "production" and self.enable_api_docs:
            raise ValueError("interactive API documentation cannot be enabled in production")
        if self.local_model_enabled and not all(
            (self.local_model_base_url, self.local_model_id, self.local_model_reader_token)
        ):
            raise ValueError("enabled local model requires base URL, model ID, and reader token")
        return self

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger("atlas")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
