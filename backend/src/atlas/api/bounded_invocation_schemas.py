from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.bounded_invocation import (
    ConnectorBoundedInvocationRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorBoundedInvocationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-bounded-invocation-input.v1", pattern=STABLE_ID
    )
    source_authorization_id: str = Field(pattern=STABLE_ID)
    source_authorization_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    invocation_policy_id: str = Field(pattern=STABLE_ID)
    invocation_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_authorization_is_consumed_once_without_retry_on_uncertain_outcome: bool


class ConnectorBoundedInvocationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invocation_id: str
    schema_version: str
    version: int
    consumption_claim_id: str
    source_authorization_id: str
    source_authorization_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    connector_id: str
    release_version: str
    manifest_digest: str
    instance_id: str
    instance_key: str
    display_name: str
    capability_id: str
    capability_class: str
    required_permission: str
    invocation_profile_id: str
    invocation_profile_digest: str
    input_envelope_id: str
    input_envelope_digest: str
    input_schema_digest: str
    output_schema_digest: str
    result_policy_digest: str
    invocation_policy_id: str
    invocation_policy_digest: str
    invocation_policy_version: str
    invocation_adapter_id: str
    normalized_redacted_result_digest: str
    observation_count: int
    output_bytes: int
    instance_state: str
    invoked_by: str
    purpose: str
    started_at: datetime
    completed_at: datetime
    canonical_digest: str
    authorization_consumed: bool
    target_connection_opened: bool
    capability_invoked: bool
    result_received: bool
    result_validated: bool
    result_redacted: bool
    target_session_closed: bool
    delivery_channel_closed: bool
    lease_revocation_confirmed: bool
    target_connected: bool
    reusable_session_available: bool
    scheduled: bool
    evidence_ingested: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, record: ConnectorBoundedInvocationRecord
    ) -> ConnectorBoundedInvocationData:
        return cls.model_validate(record, from_attributes=True)


class ConnectorBoundedInvocationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorBoundedInvocationData
    meta: ResponseMeta
