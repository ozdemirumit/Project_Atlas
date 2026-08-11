from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.instance_creation import (
    ConnectorInstanceCreationPolicySnapshot,
    ConnectorInstanceRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorInstanceCreationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-instance-creation-input.v1", pattern=STABLE_ID
    )
    source_installation_receipt_id: str = Field(pattern=STABLE_ID)
    source_installation_receipt_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    instance_key: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    display_name: str = Field(min_length=3, max_length=200)
    instance_policy_id: str = Field(pattern=STABLE_ID)
    instance_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_instance_is_disabled_and_grants_no_target_or_runtime_authority: bool


class ConnectorInstanceRetirementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-instance-retirement-input.v1", pattern=STABLE_ID
    )
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=20, max_length=1000)
    acknowledged_retirement_preserves_history_and_performs_no_runtime_action: bool


class ConnectorInstanceCreationPolicyData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    allowed_sdk_profiles: tuple[str, ...]
    allowed_capability_classes: tuple[str, ...]
    required_initial_state: str
    maximum_instance_key_length: int
    maximum_display_name_length: int
    expires_at: datetime
    canonical_digest: str

    @classmethod
    def from_domain(
        cls, policy: ConnectorInstanceCreationPolicySnapshot
    ) -> ConnectorInstanceCreationPolicyData:
        return cls(**{field: getattr(policy, field) for field in cls.model_fields})


class ConnectorInstanceRecordData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    schema_version: str
    version: int
    source_installation_receipt_id: str
    source_installation_receipt_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    connector_id: str
    release_version: str
    manifest_digest: str
    sdk_profile: str
    instance_policy_id: str
    instance_policy_digest: str
    instance_policy_version: str
    instance_id: str
    instance_key: str
    display_name: str
    instance_state: str
    owner_id: str
    support_group_id: str
    created_by: str
    purpose: str
    created_at: datetime
    canonical_digest: str
    package_published: bool
    connector_registered: bool
    package_installed: bool
    instance_created: bool
    eligible_for_configuration_governance: bool
    promotion_blocked: bool
    target_configured: bool
    credentials_resolved: bool
    connector_enabled: bool
    runtime_trust_granted: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool
    retired_by: str | None
    retired_at: datetime | None
    retirement_reason: str | None

    @classmethod
    def from_domain(cls, record: ConnectorInstanceRecord) -> ConnectorInstanceRecordData:
        return cls(**{field: getattr(record, field) for field in cls.model_fields})


class ConnectorInstanceCreationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorInstanceRecordData
    meta: ResponseMeta


class ConnectorInstanceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorInstanceRecordData, ...]
    meta: ResponseMeta


class ConnectorInstanceCreationPolicyListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorInstanceCreationPolicyData, ...]
    meta: ResponseMeta
