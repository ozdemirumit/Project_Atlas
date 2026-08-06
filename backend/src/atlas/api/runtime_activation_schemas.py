from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.runtime_activation import ConnectorRuntimeActivationRecord

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorRuntimeActivationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-runtime-activation-input.v1", pattern=STABLE_ID
    )
    source_brokerage_authorization_id: str = Field(pattern=STABLE_ID)
    source_brokerage_authorization_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    activation_profile_id: str = Field(pattern=STABLE_ID)
    activation_profile_digest: str = Field(pattern=DIGEST)
    activation_policy_id: str = Field(pattern=STABLE_ID)
    activation_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_activation_grants_no_target_connection_invocation_execution_or_deployment: bool


class RuntimeHealthProbeData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    probe_id: str
    outcome: str


class ConnectorRuntimeActivationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activation_id: str
    schema_version: str
    version: int
    source_brokerage_authorization_id: str
    source_brokerage_authorization_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    connector_id: str
    release_version: str
    manifest_digest: str
    instance_id: str
    instance_key: str
    display_name: str
    runtime_profile_digest: str
    runner_identity_digest: str
    image_digest: str
    workload_identity_digest: str
    activation_profile_id: str
    activation_profile_digest: str
    activation_policy_id: str
    activation_policy_digest: str
    activation_policy_version: str
    activation_adapter_id: str
    health_probe_results: tuple[RuntimeHealthProbeData, ...]
    instance_state: str
    activated_by: str
    purpose: str
    activated_at: datetime
    healthy_at: datetime
    canonical_digest: str
    runtime_boundary_bound: bool
    runtime_trust_granted: bool
    secret_brokerage_governed: bool
    credential_resolution_authorized: bool
    secret_lease_issued: bool
    credentials_resolved: bool
    runner_started: bool
    package_loaded: bool
    runtime_health_verified: bool
    lease_delivery_completed: bool
    delivery_channel_closed: bool
    lease_revocation_confirmed: bool
    eligible_for_target_session_authorization: bool
    target_connected: bool
    target_connection_authorized: bool
    capability_invocation_authorized: bool
    capability_invoked: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, record: ConnectorRuntimeActivationRecord
    ) -> ConnectorRuntimeActivationData:
        return cls.model_validate(record, from_attributes=True)


class ConnectorRuntimeActivationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorRuntimeActivationData
    meta: ResponseMeta
