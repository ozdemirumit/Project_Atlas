from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.invocation_authorization import (
    ConnectorInvocationAuthorizationRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorInvocationAuthorizationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-invocation-authorization-input.v1", pattern=STABLE_ID
    )
    source_target_session_verification_id: str = Field(pattern=STABLE_ID)
    source_target_session_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    capability_id: str = Field(pattern=STABLE_ID)
    invocation_profile_id: str = Field(pattern=STABLE_ID)
    invocation_profile_digest: str = Field(pattern=DIGEST)
    input_envelope_id: str = Field(pattern=STABLE_ID)
    input_envelope_digest: str = Field(pattern=DIGEST)
    authorization_policy_id: str = Field(pattern=STABLE_ID)
    authorization_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_single_use_authorization_grants_no_invocation_schedule_execution_or_deployment: (
        bool
    )


class ConnectorInvocationAuthorizationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_id: str
    schema_version: str
    version: int
    source_target_session_verification_id: str
    source_target_session_digest: str
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
    capability_id: str
    capability_class: str
    required_permission: str
    invocation_profile_id: str
    invocation_profile_digest: str
    input_envelope_id: str
    input_envelope_digest: str
    input_envelope_schema: str
    normalized_input_digest: str
    input_schema_digest: str
    output_schema_digest: str
    result_policy_digest: str
    maximum_timeout_seconds: int
    maximum_output_bytes: int
    authorization_policy_id: str
    authorization_policy_digest: str
    authorization_policy_version: str
    instance_state: str
    authorized_by: str
    purpose: str
    authorized_at: datetime
    expires_at: datetime
    canonical_digest: str
    target_session_verified: bool
    capability_enabled: bool
    capability_permission_verified: bool
    capability_invocation_authorized: bool
    eligible_for_bounded_capability_invocation: bool
    single_use: bool
    renewable: bool
    consumed: bool
    target_connected: bool
    capability_invoked: bool
    scheduled: bool
    result_received: bool
    result_validated: bool
    evidence_ingested: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, record: ConnectorInvocationAuthorizationRecord
    ) -> ConnectorInvocationAuthorizationData:
        return cls.model_validate(record, from_attributes=True)


class ConnectorInvocationAuthorizationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorInvocationAuthorizationData
    meta: ResponseMeta
