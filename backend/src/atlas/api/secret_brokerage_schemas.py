from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.secret_brokerage import (
    ConnectorSecretBrokerageAuthorizationRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorSecretBrokerageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-secret-brokerage-input.v1", pattern=STABLE_ID
    )
    source_runtime_trust_grant_id: str = Field(pattern=STABLE_ID)
    source_runtime_trust_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    brokerage_profile_id: str = Field(pattern=STABLE_ID)
    brokerage_profile_digest: str = Field(pattern=DIGEST)
    brokerage_policy_id: str = Field(pattern=STABLE_ID)
    brokerage_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_authorization_grants_no_lease_secret_runtime_target_execution_or_deployment: bool


class ConnectorSecretBrokerageData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_id: str
    schema_version: str
    version: int
    source_runtime_trust_grant_id: str
    source_runtime_trust_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    connector_id: str
    release_version: str
    manifest_digest: str
    instance_id: str
    instance_key: str
    display_name: str
    credential_class: str
    authentication_method: str
    privilege_class: str
    rotation_state: str
    revocation_state: str
    next_rotation_at: datetime
    runtime_profile_id: str
    runtime_profile_digest: str
    runner_workload_identity_id: str
    secret_delivery_policy_id: str
    brokerage_profile_id: str
    brokerage_profile_digest: str
    delivery_policy_id: str
    lease_policy_id: str
    maximum_lease_seconds: int
    revocation_policy_id: str
    brokerage_policy_id: str
    brokerage_policy_digest: str
    brokerage_policy_version: str
    authorization_version: int
    instance_state: str
    authorized_by: str
    purpose: str
    authorized_at: datetime
    canonical_digest: str
    runtime_boundary_bound: bool
    runtime_trust_granted: bool
    eligible_for_secret_brokerage: bool
    secret_brokerage_governed: bool
    credential_resolution_authorized: bool
    eligible_for_runtime_activation: bool
    promotion_blocked: bool
    secret_lease_issued: bool
    credentials_resolved: bool
    runner_started: bool
    package_loaded: bool
    target_connection_authorized: bool
    capability_invocation_authorized: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, record: ConnectorSecretBrokerageAuthorizationRecord
    ) -> ConnectorSecretBrokerageData:
        return cls.model_validate(record, from_attributes=True)


class ConnectorSecretBrokerageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorSecretBrokerageData
    meta: ResponseMeta
