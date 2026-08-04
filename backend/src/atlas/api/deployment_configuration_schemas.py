from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.platform.domain.deployment_configuration import (
    DeploymentConfigurationOverlay,
    DeploymentConfigurationPreview,
    DeploymentConfigurationRequest,
    NamedBooleanValue,
    NamedStringValue,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class NamedStringValueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3, max_length=128)
    value: str = Field(min_length=1, max_length=2048)


class NamedBooleanValueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3, max_length=128)
    value: bool


class DeploymentConfigurationOverlayInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_bind: str | None = Field(default=None, min_length=1, max_length=255)
    public_url: str | None = Field(default=None, min_length=1, max_length=2048)
    cors_origins: list[str] | None = Field(default=None, max_length=32)
    component_references: list[NamedStringValueInput] | None = Field(default=None, max_length=64)
    feature_flags: list[NamedBooleanValueInput] | None = Field(default=None, max_length=64)
    integration_endpoints: list[NamedStringValueInput] | None = Field(default=None, max_length=64)
    resource_names: list[str] | None = Field(default=None, max_length=128)
    secret_references: list[NamedStringValueInput] | None = Field(default=None, max_length=128)

    def to_domain(self) -> DeploymentConfigurationOverlay:
        return DeploymentConfigurationOverlay(
            api_bind=self.api_bind,
            public_url=self.public_url,
            cors_origins=None if self.cors_origins is None else tuple(self.cors_origins),
            component_references=(
                None
                if self.component_references is None
                else tuple(
                    NamedStringValue(item.name, item.value) for item in self.component_references
                )
            ),
            feature_flags=(
                None
                if self.feature_flags is None
                else tuple(NamedBooleanValue(item.name, item.value) for item in self.feature_flags)
            ),
            integration_endpoints=(
                None
                if self.integration_endpoints is None
                else tuple(
                    NamedStringValue(item.name, item.value) for item in self.integration_endpoints
                )
            ),
            resource_names=None if self.resource_names is None else tuple(self.resource_names),
            secret_references=(
                None
                if self.secret_references is None
                else tuple(
                    NamedStringValue(item.name, item.value) for item in self.secret_references
                )
            ),
        )


class DeploymentConfigurationPreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.deployment-configuration-request.v1"]
    release_id: str = Field(min_length=3, max_length=128)
    profile: DeploymentProfile
    organization_id: str = Field(min_length=3, max_length=128)
    environment_id: str = Field(min_length=3, max_length=128)
    site_id: str = Field(min_length=3, max_length=128)
    overlay: DeploymentConfigurationOverlayInput = Field(
        default_factory=DeploymentConfigurationOverlayInput
    )

    def to_domain(self) -> DeploymentConfigurationRequest:
        return DeploymentConfigurationRequest(
            schema_version=self.schema_version,
            release_id=self.release_id,
            profile=self.profile,
            organization_id=self.organization_id,
            environment_id=self.environment_id,
            site_id=self.site_id,
            overlay=self.overlay.to_domain(),
        )


class ConfigurationValidationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    state: str
    summary: str
    evidence: str
    remediation: str | None


class EffectiveConfigurationFieldData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    display_value: str
    source: str
    sensitive: bool


class DeploymentConfigurationPreviewData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_id: str
    schema_version: str
    release_id: str
    profile: str
    organization_id: str
    environment_id: str
    site_id: str
    state: str
    configuration_digest: str
    fields: list[EffectiveConfigurationFieldData]
    validations: list[ConfigurationValidationData]
    generated_at: datetime
    correlation_id: str
    mutation_authorized: bool
    execution_authorized: bool

    @classmethod
    def from_domain(
        cls, preview: DeploymentConfigurationPreview
    ) -> DeploymentConfigurationPreviewData:
        return cls(
            preview_id=preview.preview_id,
            schema_version=preview.schema_version,
            release_id=preview.release_id,
            profile=preview.profile.value,
            organization_id=preview.organization_id,
            environment_id=preview.environment_id,
            site_id=preview.site_id,
            state=preview.state.value,
            configuration_digest=preview.configuration_digest,
            fields=[
                EffectiveConfigurationFieldData(
                    path=item.path,
                    display_value=item.display_value,
                    source=item.source.value,
                    sensitive=item.sensitive,
                )
                for item in preview.fields
            ],
            validations=[
                ConfigurationValidationData(
                    code=item.code,
                    state=item.state.value,
                    summary=item.summary,
                    evidence=item.evidence,
                    remediation=item.remediation,
                )
                for item in preview.validations
            ],
            generated_at=preview.generated_at,
            correlation_id=preview.correlation_id,
            mutation_authorized=preview.mutation_authorized,
            execution_authorized=preview.execution_authorized,
        )


class DeploymentConfigurationPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: DeploymentConfigurationPreviewData
    meta: ResponseMeta
