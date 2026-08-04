from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class ConfigurationState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class ConfigurationValueSource(StrEnum):
    RELEASE_DEFAULT = "release_default"
    OVERLAY = "overlay"


@dataclass(frozen=True, slots=True)
class NamedStringValue:
    name: str
    value: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.name, "configuration value name")
        if not 1 <= len(self.value) <= 2048 or any(ord(item) < 32 for item in self.value):
            raise ValueError("configuration value is invalid")


@dataclass(frozen=True, slots=True)
class NamedBooleanValue:
    name: str
    value: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.name, "configuration flag name")


@dataclass(frozen=True, slots=True)
class DeploymentConfigurationOverlay:
    api_bind: str | None = None
    public_url: str | None = None
    cors_origins: tuple[str, ...] | None = None
    component_references: tuple[NamedStringValue, ...] | None = None
    feature_flags: tuple[NamedBooleanValue, ...] | None = None
    integration_endpoints: tuple[NamedStringValue, ...] | None = None
    resource_names: tuple[str, ...] | None = None
    secret_references: tuple[NamedStringValue, ...] | None = None


@dataclass(frozen=True, slots=True)
class DeploymentConfigurationRequest:
    schema_version: str
    release_id: str
    profile: DeploymentProfile
    organization_id: str
    environment_id: str
    site_id: str
    overlay: DeploymentConfigurationOverlay

    def __post_init__(self) -> None:
        if self.schema_version != "atlas.deployment-configuration-request.v1":
            raise ValueError("deployment configuration request schema is unsupported")
        for value, label in (
            (self.release_id, "release_id"),
            (self.organization_id, "organization_id"),
            (self.environment_id, "environment_id"),
            (self.site_id, "site_id"),
        ):
            validate_stable_identifier(value, label)


@dataclass(frozen=True, slots=True)
class ConfigurationValidation:
    code: str
    state: ConfigurationState
    summary: str
    evidence: str
    remediation: str | None = None


@dataclass(frozen=True, slots=True)
class EffectiveConfigurationField:
    path: str
    display_value: str
    source: ConfigurationValueSource
    sensitive: bool = False


@dataclass(frozen=True, slots=True)
class DeploymentConfigurationPreview:
    preview_id: str
    schema_version: str
    release_id: str
    profile: DeploymentProfile
    organization_id: str
    environment_id: str
    site_id: str
    state: ConfigurationState
    configuration_digest: str
    fields: tuple[EffectiveConfigurationField, ...]
    validations: tuple[ConfigurationValidation, ...]
    generated_at: datetime
    correlation_id: str
    mutation_authorized: bool = False
    execution_authorized: bool = False
