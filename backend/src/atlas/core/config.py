from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlparse

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

STABLE_CONFIG_IDENTIFIER = r"^[a-z][a-z0-9_.:-]{2,127}$"


class DirectoryGroupMappingSetting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    directory_group: str = Field(min_length=1, max_length=512)
    atlas_group_id: str = Field(pattern=STABLE_CONFIG_IDENTIFIER)
    role_ids: tuple[str, ...]

    @model_validator(mode="after")
    def validate_mapping(self) -> Self:
        if any(ord(character) < 32 for character in self.directory_group):
            raise ValueError("directory group mapping contains control characters")
        if not self.role_ids or any(
            re.fullmatch(STABLE_CONFIG_IDENTIFIER, item) is None for item in self.role_ids
        ):
            raise ValueError("directory group mapping role identifiers are invalid")
        return self


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
    bootstrap_artifact_root: Path = Path(".atlas/bootstrap-artifacts")
    bootstrap_artifact_max_total_bytes: int = Field(
        default=4 * 1024 * 1024 * 1024, ge=1, le=64 * 1024 * 1024 * 1024
    )
    bootstrap_configuration_root: Path = Path(".atlas/bootstrap-configurations")
    bootstrap_configuration_max_bytes: int = Field(
        default=1024 * 1024, ge=1024, le=16 * 1024 * 1024
    )
    bootstrap_trust_root: Path = Path(".atlas/bootstrap-trust")
    bootstrap_trust_max_total_bytes: int = Field(
        default=4 * 1024 * 1024, ge=1024, le=64 * 1024 * 1024
    )
    bootstrap_data_root: Path = Path(".atlas/bootstrap-data")
    bootstrap_data_max_state_bytes: int = Field(
        default=4 * 1024 * 1024, ge=1024, le=64 * 1024 * 1024
    )
    bootstrap_service_root: Path = Path(".atlas/bootstrap-services")
    bootstrap_service_max_state_bytes: int = Field(
        default=4 * 1024 * 1024, ge=1024, le=64 * 1024 * 1024
    )
    bootstrap_identity_root: Path = Path(".atlas/bootstrap-identity")
    bootstrap_identity_max_state_bytes: int = Field(
        default=4 * 1024 * 1024, ge=1024, le=64 * 1024 * 1024
    )
    bootstrap_integration_root: Path = Path(".atlas/bootstrap-integrations")
    bootstrap_integration_max_state_bytes: int = Field(
        default=4 * 1024 * 1024, ge=1024, le=64 * 1024 * 1024
    )
    bootstrap_verification_root: Path = Path(".atlas/bootstrap-verification")
    bootstrap_verification_max_report_bytes: int = Field(
        default=4 * 1024 * 1024, ge=1024, le=64 * 1024 * 1024
    )
    bootstrap_handoff_root: Path = Path(".atlas/bootstrap-handoff")
    bootstrap_handoff_max_report_bytes: int = Field(
        default=4 * 1024 * 1024, ge=1024, le=64 * 1024 * 1024
    )
    support_bundle_root: Path = Path(".atlas/support-bundles")
    support_bundle_max_content_bytes: int = Field(
        default=2 * 1024 * 1024, ge=1024, le=32 * 1024 * 1024
    )
    support_bundle_max_archive_bytes: int = Field(
        default=4 * 1024 * 1024, ge=2048, le=64 * 1024 * 1024
    )
    logical_backup_root: Path = Path(".atlas/logical-backups")
    logical_backup_max_content_bytes: int = Field(
        default=4 * 1024 * 1024, ge=1024, le=32 * 1024 * 1024
    )
    logical_backup_max_archive_bytes: int = Field(
        default=8 * 1024 * 1024, ge=2048, le=64 * 1024 * 1024
    )
    cors_origins: tuple[AnyHttpUrl, ...] = (AnyHttpUrl("http://localhost:5173"),)
    development_identity_enabled: bool = False
    development_subject_id: str = "subject.development.operator"
    development_display_name: str = "Local Operator"
    development_organization_id: str = "organization.development"
    development_role_ids: tuple[str, ...] = ("role.development.operator",)
    directory_identity_enabled: bool = False
    directory_provider_id: str = Field(
        default="provider.ldap.enterprise", pattern=STABLE_CONFIG_IDENTIFIER
    )
    directory_organization_id: str = Field(
        default="organization.development", pattern=STABLE_CONFIG_IDENTIFIER
    )
    directory_endpoints: tuple[str, ...] = ()
    directory_ca_certificate_file: Path | None = None
    directory_user_principal_template: str = "{username}"
    directory_user_search_base: str = ""
    directory_user_search_filter: str = "(&(objectClass=person)(sAMAccountName={username}))"
    directory_stable_id_attribute: str = "objectGUID"
    directory_display_name_attribute: str = "displayName"
    directory_group_attribute: str = "memberOf"
    directory_group_mappings: tuple[DirectoryGroupMappingSetting, ...] = ()
    directory_max_groups: int = Field(default=100, ge=1, le=500)
    directory_nested_group_depth: int = Field(default=0, ge=0, le=5)
    directory_connect_timeout_seconds: float = Field(default=3.0, ge=0.1, le=15)
    directory_response_timeout_seconds: float = Field(default=5.0, ge=0.1, le=30)
    session_cookie_name: str = Field(default="atlas_session", pattern=r"^[A-Za-z0-9_-]{3,64}$")
    csrf_cookie_name: str = Field(default="atlas_csrf", pattern=r"^[A-Za-z0-9_-]{3,64}$")
    csrf_header_name: str = Field(default="X-CSRF-Token", pattern=r"^X-[A-Za-z0-9-]{3,64}$")
    session_absolute_timeout_minutes: int = Field(default=480, ge=5, le=1440)
    session_idle_timeout_minutes: int = Field(default=30, ge=1, le=240)
    session_max_per_subject: int = Field(default=5, ge=1, le=20)
    api_credential_max_lifetime_minutes: int = Field(default=60, ge=5, le=60)
    api_credential_max_active_per_subject: int = Field(default=10, ge=1, le=20)
    local_model_enabled: bool = False
    local_model_base_url: AnyHttpUrl | None = None
    local_model_id: str | None = None
    local_model_reader_token: SecretStr | None = None
    local_model_secret_reference_id: str = "secret.model.local-reader"

    @model_validator(mode="after")
    def enforce_production_security_defaults(self) -> Self:
        if self.environment == "production" and self.development_identity_enabled:
            raise ValueError("development identity cannot be enabled in production")
        if self.development_identity_enabled and self.directory_identity_enabled:
            raise ValueError("development and directory identity cannot be enabled together")
        if self.directory_identity_enabled:
            if not self.directory_endpoints:
                raise ValueError("enabled directory identity requires at least one endpoint")
            parsed_endpoints = tuple(urlparse(item) for item in self.directory_endpoints)
            if any(
                item.scheme != "ldaps"
                or not item.hostname
                or item.username
                or item.password
                or item.query
                or item.fragment
                or item.path not in {"", "/"}
                for item in parsed_endpoints
            ):
                raise ValueError("directory identity requires ldaps endpoints")
            if self.directory_ca_certificate_file is None:
                raise ValueError("directory identity requires a CA certificate file")
            if not self.directory_user_search_base.strip():
                raise ValueError("directory identity requires a user search base")
            for template, label in (
                (self.directory_user_principal_template, "principal"),
                (self.directory_user_search_filter, "search filter"),
            ):
                remainder = template.replace("{username}", "")
                if (
                    template.count("{username}") != 1
                    or "{" in remainder
                    or "}" in remainder
                    or any(ord(character) < 32 for character in template)
                ):
                    raise ValueError(f"directory identity {label} template is invalid")
            if self.directory_nested_group_depth != 0:
                raise ValueError("nested directory groups are not supported in this slice")
        if self.environment == "production" and self.enable_api_docs:
            raise ValueError("interactive API documentation cannot be enabled in production")
        if self.local_model_enabled and not all(
            (self.local_model_base_url, self.local_model_id, self.local_model_reader_token)
        ):
            raise ValueError("enabled local model requires base URL, model ID, and reader token")
        if self.session_idle_timeout_minutes > self.session_absolute_timeout_minutes:
            raise ValueError("session idle timeout cannot exceed absolute timeout")
        return self

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger("atlas")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
