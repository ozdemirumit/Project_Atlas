from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.application.capability_enablement import (
    ConnectorCapabilityEnablementOption,
)
from atlas.modules.connectors.domain.capability_enablement import (
    ConnectorCapabilityEnablementRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorCapabilityEnablementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-capability-enablement-input.v1", pattern=STABLE_ID
    )
    source_validation_id: str = Field(pattern=STABLE_ID)
    source_validation_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    capability_profile_id: str = Field(pattern=STABLE_ID)
    capability_profile_digest: str = Field(pattern=DIGEST)
    enablement_policy_id: str = Field(pattern=STABLE_ID)
    enablement_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_enablement_grants_no_secret_runtime_execution_or_deployment_authority: bool


class ConnectorGovernedCapabilityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    capability_class: str
    required_permission: str


class ConnectorCapabilityEnablementData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enablement_id: str
    schema_version: str
    version: int
    source_validation_id: str
    source_validation_digest: str
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
    credential_profile_id: str
    credential_profile_digest: str
    capability_profile_id: str
    capability_profile_digest: str
    capabilities: tuple[ConnectorGovernedCapabilityData, ...]
    enablement_policy_id: str
    enablement_policy_digest: str
    enablement_policy_version: str
    enablement_version: int
    instance_state: str
    enabled_by: str
    purpose: str
    enabled_at: datetime
    canonical_digest: str
    configuration_validated: bool
    connectivity_evidence_verified: bool
    eligible_for_capability_governance: bool
    capability_governance_applied: bool
    connector_enabled: bool
    eligible_for_runtime_trust: bool
    promotion_blocked: bool
    credentials_resolved: bool
    runtime_trust_granted: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, record: ConnectorCapabilityEnablementRecord
    ) -> ConnectorCapabilityEnablementData:
        return cls.model_validate(record, from_attributes=True)


class ConnectorCapabilityEnablementInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enablement_id: str
    source_validation_id: str
    connector_id: str
    release_version: str
    instance_id: str
    display_name: str
    capability_profile_id: str
    capabilities: tuple[ConnectorGovernedCapabilityData, ...]
    enablement_policy_id: str
    enablement_policy_version: str
    instance_state: Literal["enabled_capabilities_governed"]
    enabled_by: str
    purpose: str
    enabled_at: datetime
    configuration_validated: Literal[True]
    connectivity_evidence_verified: Literal[True]
    eligible_for_capability_governance: Literal[True]
    capability_governance_applied: Literal[True]
    connector_enabled: Literal[True]
    eligible_for_runtime_trust: Literal[True]
    credentials_resolved: Literal[False]
    runtime_trust_granted: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_domain(
        cls, record: ConnectorCapabilityEnablementRecord
    ) -> ConnectorCapabilityEnablementInventoryData:
        return cls(
            **{
                field: getattr(record, field)
                for field in cls.model_fields
                if field != "capabilities"
            },
            capabilities=tuple(
                ConnectorGovernedCapabilityData.model_validate(item, from_attributes=True)
                for item in record.capabilities
            ),
        )


class ConnectorCapabilityEnablementInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorCapabilityEnablementInventoryData, ...]
    meta: ResponseMeta


class ConnectorCapabilityEnablementViewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorCapabilityEnablementInventoryData
    meta: ResponseMeta


class ConnectorCapabilityEnablementOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_validation_id: str
    source_validation_digest: str
    package_digest: str
    capability_profile_id: str
    capability_profile_digest: str
    capabilities: tuple[ConnectorGovernedCapabilityData, ...]
    capability_profile_expires_at: datetime
    enablement_policy_id: str
    enablement_policy_digest: str
    enablement_policy_version: str
    enablement_policy_expires_at: datetime
    required_assurance_level: str
    resulting_instance_state: Literal["enabled_capabilities_governed"]
    resulting_capability_governance_applied: Literal[True]
    connector_enabled: Literal[True]
    eligible_for_runtime_trust: Literal[True]
    credentials_resolved: Literal[False]
    runtime_trust_granted: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_application(
        cls, option: ConnectorCapabilityEnablementOption
    ) -> ConnectorCapabilityEnablementOptionData:
        return cls.model_validate(
            {
                **{
                    field: getattr(option, field)
                    for field in cls.model_fields
                    if field
                    not in {
                        "capabilities",
                        "required_assurance_level",
                        "resulting_capability_governance_applied",
                        "connector_enabled",
                        "eligible_for_runtime_trust",
                        "credentials_resolved",
                        "runtime_trust_granted",
                        "execution_authorized",
                        "deployment_approved",
                        "infrastructure_mutation_performed",
                    }
                },
                "capabilities": tuple(
                    ConnectorGovernedCapabilityData.model_validate(item, from_attributes=True)
                    for item in option.capabilities
                ),
                "required_assurance_level": option.required_assurance_level.value,
                "resulting_capability_governance_applied": True,
                "connector_enabled": True,
                "eligible_for_runtime_trust": True,
                "credentials_resolved": False,
                "runtime_trust_granted": False,
                "execution_authorized": False,
                "deployment_approved": False,
                "infrastructure_mutation_performed": False,
            }
        )


class ConnectorCapabilityEnablementOptionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorCapabilityEnablementOptionData, ...]
    meta: ResponseMeta


class ConnectorCapabilityEnablementResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorCapabilityEnablementData
    meta: ResponseMeta
