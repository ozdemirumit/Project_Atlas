from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.application.target_configuration import (
    ConnectorTargetConfigurationOption,
)
from atlas.modules.connectors.domain.target_configuration import (
    ConnectorTargetConfigurationBinding,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorTargetConfigurationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-target-configuration-input.v1", pattern=STABLE_ID
    )
    source_instance_record_id: str = Field(pattern=STABLE_ID)
    source_instance_record_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    target_profile_id: str = Field(pattern=STABLE_ID)
    target_profile_digest: str = Field(pattern=DIGEST)
    configuration_policy_id: str = Field(pattern=STABLE_ID)
    configuration_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_binding_grants_no_credentials_enablement_or_runtime_authority: bool


class ConnectorTargetConfigurationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    binding_id: str
    schema_version: str
    version: int
    source_instance_record_id: str
    source_instance_record_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    connector_id: str
    release_version: str
    manifest_digest: str
    instance_id: str
    instance_key: str
    display_name: str
    owner_id: str
    target_profile_id: str
    target_profile_digest: str
    site_id: str
    target_type: str
    target_product: str
    target_version: str
    configuration_policy_id: str
    configuration_policy_digest: str
    configuration_policy_version: str
    configuration_version: int
    instance_state: str
    bound_by: str
    purpose: str
    bound_at: datetime
    canonical_digest: str
    package_installed: bool
    instance_created: bool
    target_configured: bool
    eligible_for_credential_governance: bool
    promotion_blocked: bool
    credentials_resolved: bool
    connector_enabled: bool
    runtime_trust_granted: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, binding: ConnectorTargetConfigurationBinding
    ) -> ConnectorTargetConfigurationData:
        return cls(**{field: getattr(binding, field) for field in cls.model_fields})


class ConnectorTargetConfigurationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorTargetConfigurationData
    meta: ResponseMeta


class ConnectorTargetConfigurationInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorTargetConfigurationData, ...]
    meta: ResponseMeta


class ConnectorTargetConfigurationOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_instance_record_id: str
    target_profile_id: str
    target_profile_digest: str
    site_id: str
    target_type: str
    target_product: str
    target_version: str
    target_profile_expires_at: datetime
    configuration_policy_id: str
    configuration_policy_digest: str
    configuration_policy_version: str
    configuration_policy_expires_at: datetime
    required_assurance_level: str
    resulting_instance_state: Literal["disabled_target_configured"]
    resulting_target_configured: Literal[True]
    credentials_resolved: Literal[False]
    connector_enabled: Literal[False]
    runtime_trust_granted: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_application(
        cls, option: ConnectorTargetConfigurationOption
    ) -> ConnectorTargetConfigurationOptionData:
        return cls(
            **{
                field: getattr(option, field)
                for field in cls.model_fields
                if field
                not in {
                    "required_assurance_level",
                    "resulting_target_configured",
                    "credentials_resolved",
                    "connector_enabled",
                    "runtime_trust_granted",
                    "execution_authorized",
                    "infrastructure_mutation_performed",
                }
            },
            required_assurance_level=option.required_assurance_level.value,
            resulting_target_configured=True,
            credentials_resolved=False,
            connector_enabled=False,
            runtime_trust_granted=False,
            execution_authorized=False,
            infrastructure_mutation_performed=False,
        )


class ConnectorTargetConfigurationOptionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorTargetConfigurationOptionData, ...]
    meta: ResponseMeta
