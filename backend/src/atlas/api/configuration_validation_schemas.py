from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.application.configuration_validation import (
    ConnectorConfigurationValidationOption,
)
from atlas.modules.connectors.domain.configuration_validation import (
    ConnectorConfigurationValidationRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorConfigurationValidationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-configuration-validation-input.v1", pattern=STABLE_ID
    )
    source_assignment_id: str = Field(pattern=STABLE_ID)
    source_assignment_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    evidence_id: str = Field(pattern=STABLE_ID)
    evidence_digest: str = Field(pattern=DIGEST)
    validation_policy_id: str = Field(pattern=STABLE_ID)
    validation_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_validation_grants_no_secret_network_enablement_or_runtime_authority: bool


class ConnectorConfigurationValidationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_id: str
    schema_version: str
    version: int
    source_assignment_id: str
    source_assignment_digest: str
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
    credential_class: str
    authentication_method: str
    privilege_class: str
    evidence_id: str
    evidence_digest: str
    probe_runner_id: str
    probe_runner_version: str
    network_zone_id: str
    configuration_result: str
    connectivity_result: str
    tls_result: str
    endpoint_identity_result: str
    authentication_result: str
    authorization_result: str
    product_identity_result: str
    latency_band: str
    completed_checks: tuple[str, ...]
    evidence_observed_at: datetime
    validation_policy_id: str
    validation_policy_digest: str
    validation_policy_version: str
    validation_version: int
    instance_state: str
    validated_by: str
    purpose: str
    validated_at: datetime
    canonical_digest: str
    package_installed: bool
    instance_created: bool
    target_configured: bool
    credential_references_assigned: bool
    eligible_for_configuration_validation: bool
    configuration_validated: bool
    connectivity_evidence_verified: bool
    eligible_for_capability_governance: bool
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
        cls, record: ConnectorConfigurationValidationRecord
    ) -> ConnectorConfigurationValidationData:
        return cls(**{field: getattr(record, field) for field in cls.model_fields})


class ConnectorConfigurationValidationInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_id: str
    source_assignment_id: str
    connector_id: str
    release_version: str
    instance_id: str
    display_name: str
    evidence_id: str
    configuration_result: str
    connectivity_result: str
    tls_result: str
    endpoint_identity_result: str
    authentication_result: str
    authorization_result: str
    product_identity_result: str
    latency_band: str
    completed_checks: tuple[str, ...]
    evidence_observed_at: datetime
    validation_policy_id: str
    validation_policy_version: str
    instance_state: Literal["disabled_configuration_validated"]
    validated_by: str
    purpose: str
    validated_at: datetime
    configuration_validated: Literal[True]
    connectivity_evidence_verified: Literal[True]
    eligible_for_capability_governance: Literal[True]
    credentials_resolved: Literal[False]
    connector_enabled: Literal[False]
    runtime_trust_granted: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_domain(
        cls, record: ConnectorConfigurationValidationRecord
    ) -> ConnectorConfigurationValidationInventoryData:
        return cls(**{field: getattr(record, field) for field in cls.model_fields})


class ConnectorConfigurationValidationInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorConfigurationValidationInventoryData, ...]
    meta: ResponseMeta


class ConnectorConfigurationValidationOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_assignment_id: str
    source_assignment_digest: str
    package_digest: str
    evidence_id: str
    evidence_digest: str
    evidence_observed_at: datetime
    evidence_expires_at: datetime
    configuration_result: str
    connectivity_result: str
    tls_result: str
    endpoint_identity_result: str
    authentication_result: str
    authorization_result: str
    product_identity_result: str
    latency_band: str
    completed_checks: tuple[str, ...]
    validation_policy_id: str
    validation_policy_digest: str
    validation_policy_version: str
    validation_policy_expires_at: datetime
    required_assurance_level: str
    resulting_instance_state: Literal["disabled_configuration_validated"]
    resulting_configuration_validated: Literal[True]
    resulting_connectivity_evidence_verified: Literal[True]
    eligible_for_capability_governance: Literal[True]
    credentials_resolved: Literal[False]
    connector_enabled: Literal[False]
    runtime_trust_granted: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_application(
        cls, option: ConnectorConfigurationValidationOption
    ) -> ConnectorConfigurationValidationOptionData:
        return cls(
            **{
                field: getattr(option, field)
                for field in cls.model_fields
                if field
                not in {
                    "required_assurance_level",
                    "resulting_configuration_validated",
                    "resulting_connectivity_evidence_verified",
                    "eligible_for_capability_governance",
                    "credentials_resolved",
                    "connector_enabled",
                    "runtime_trust_granted",
                    "execution_authorized",
                    "deployment_approved",
                    "infrastructure_mutation_performed",
                }
            },
            required_assurance_level=option.required_assurance_level.value,
            resulting_configuration_validated=True,
            resulting_connectivity_evidence_verified=True,
            eligible_for_capability_governance=True,
            credentials_resolved=False,
            connector_enabled=False,
            runtime_trust_granted=False,
            execution_authorized=False,
            deployment_approved=False,
            infrastructure_mutation_performed=False,
        )


class ConnectorConfigurationValidationOptionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorConfigurationValidationOptionData, ...]
    meta: ResponseMeta


class ConnectorConfigurationValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorConfigurationValidationData
    meta: ResponseMeta
