from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.runtime_trust import ConnectorRuntimeTrustGrantRecord

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorRuntimeTrustInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="atlas.connector-runtime-trust-input.v1", pattern=STABLE_ID)
    source_enablement_id: str = Field(pattern=STABLE_ID)
    source_enablement_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    runtime_profile_id: str = Field(pattern=STABLE_ID)
    runtime_profile_digest: str = Field(pattern=DIGEST)
    trust_policy_id: str = Field(pattern=STABLE_ID)
    trust_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_trust_grants_no_runtime_start_secret_target_execution_or_deployment_authority: bool


class ConnectorRuntimeTrustData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grant_id: str
    schema_version: str
    version: int
    source_enablement_id: str
    source_enablement_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    connector_id: str
    release_version: str
    manifest_digest: str
    instance_id: str
    instance_key: str
    display_name: str
    capability_profile_id: str
    capability_profile_digest: str
    capability_count: int
    runtime_profile_id: str
    runtime_profile_digest: str
    sdk_profile: str
    runner_runtime_id: str
    runner_pool_id: str
    runner_image_digest: str
    runner_workload_identity_id: str
    isolation_profile_id: str
    filesystem_policy_id: str
    egress_policy_id: str
    secret_delivery_policy_id: str
    telemetry_policy_id: str
    resource_limit_profile_id: str
    trust_policy_id: str
    trust_policy_digest: str
    trust_policy_version: str
    trust_version: int
    instance_state: str
    granted_by: str
    purpose: str
    granted_at: datetime
    canonical_digest: str
    configuration_validated: bool
    connectivity_evidence_verified: bool
    capability_governance_applied: bool
    connector_enabled: bool
    eligible_for_runtime_trust: bool
    runtime_boundary_bound: bool
    runtime_trust_granted: bool
    eligible_for_secret_brokerage: bool
    promotion_blocked: bool
    runner_started: bool
    package_loaded: bool
    credential_resolution_authorized: bool
    credentials_resolved: bool
    target_connection_authorized: bool
    capability_invocation_authorized: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(cls, record: ConnectorRuntimeTrustGrantRecord) -> ConnectorRuntimeTrustData:
        return cls.model_validate(record, from_attributes=True)


class ConnectorRuntimeTrustResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorRuntimeTrustData
    meta: ResponseMeta
