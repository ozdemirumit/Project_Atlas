from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
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


class ConnectorConfigurationValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorConfigurationValidationData
    meta: ResponseMeta
