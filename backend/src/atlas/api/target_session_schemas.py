from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.target_session import (
    ConnectorTargetSessionVerificationRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorTargetSessionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-target-session-input.v1", pattern=STABLE_ID
    )
    source_runtime_activation_id: str = Field(pattern=STABLE_ID)
    source_runtime_activation_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    session_profile_id: str = Field(pattern=STABLE_ID)
    session_profile_digest: str = Field(pattern=DIGEST)
    session_policy_id: str = Field(pattern=STABLE_ID)
    session_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_bounded_session_grants_no_invocation_execution_or_deployment: bool


class TargetConnectivityCheckData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str
    outcome: str


class ConnectorTargetSessionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verification_id: str
    schema_version: str
    version: int
    source_runtime_activation_id: str
    source_runtime_activation_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    connector_id: str
    release_version: str
    manifest_digest: str
    instance_id: str
    instance_key: str
    display_name: str
    target_profile_digest: str
    target_identity_digest: str
    expected_target_product: str
    protocol_classification: str
    tls_classification: str
    session_profile_id: str
    session_profile_digest: str
    session_policy_id: str
    session_policy_digest: str
    session_policy_version: str
    session_adapter_id: str
    connectivity_check_results: tuple[TargetConnectivityCheckData, ...]
    instance_state: str
    verified_by: str
    purpose: str
    verified_at: datetime
    canonical_digest: str
    runtime_health_verified: bool
    secret_brokerage_governed: bool
    target_connection_authorized: bool
    target_connectivity_verified: bool
    target_identity_verified: bool
    read_only_session_verified: bool
    target_session_established: bool
    target_session_closed: bool
    delivery_channel_closed: bool
    lease_revocation_confirmed: bool
    eligible_for_capability_invocation_governance: bool
    target_connected: bool
    capability_invocation_authorized: bool
    capability_invoked: bool
    scheduled: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, record: ConnectorTargetSessionVerificationRecord
    ) -> ConnectorTargetSessionData:
        return cls.model_validate(record, from_attributes=True)


class ConnectorTargetSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorTargetSessionData
    meta: ResponseMeta
