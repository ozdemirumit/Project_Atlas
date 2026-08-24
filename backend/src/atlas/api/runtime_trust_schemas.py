from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.application.runtime_trust import ConnectorRuntimeTrustOption
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


class ConnectorRuntimeTrustInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grant_id: str
    source_enablement_id: str
    connector_id: str
    release_version: str
    instance_id: str
    display_name: str
    capability_profile_id: str
    capability_count: int
    runtime_profile_id: str
    sdk_profile: str
    runner_runtime_id: str
    runner_image_digest: str
    runner_workload_identity_id: str
    isolation_profile_id: str
    filesystem_policy_id: str
    egress_policy_id: str
    telemetry_policy_id: str
    resource_limit_profile_id: str
    trust_policy_id: str
    trust_policy_version: str
    trust_version: int
    instance_state: Literal["enabled_runtime_trusted"]
    granted_by: str
    purpose: str
    granted_at: datetime
    configuration_validated: Literal[True]
    connectivity_evidence_verified: Literal[True]
    capability_governance_applied: Literal[True]
    connector_enabled: Literal[True]
    eligible_for_runtime_trust: Literal[True]
    runtime_boundary_bound: Literal[True]
    runtime_trust_granted: Literal[True]
    eligible_for_secret_brokerage: Literal[True]
    runner_started: Literal[False]
    package_loaded: Literal[False]
    credential_resolution_authorized: Literal[False]
    credentials_resolved: Literal[False]
    target_connection_authorized: Literal[False]
    capability_invocation_authorized: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_domain(
        cls, record: ConnectorRuntimeTrustGrantRecord
    ) -> ConnectorRuntimeTrustInventoryData:
        return cls(**{field: getattr(record, field) for field in cls.model_fields})


class ConnectorRuntimeTrustInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorRuntimeTrustInventoryData, ...]
    meta: ResponseMeta


class ConnectorRuntimeTrustViewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorRuntimeTrustInventoryData
    meta: ResponseMeta


class ConnectorRuntimeTrustOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_enablement_id: str
    source_enablement_digest: str
    package_digest: str
    runtime_profile_id: str
    runtime_profile_digest: str
    runtime_profile_expires_at: datetime
    sdk_profile: str
    runner_runtime_id: str
    runner_image_digest: str
    runner_workload_identity_id: str
    isolation_profile_id: str
    filesystem_policy_id: str
    egress_policy_id: str
    telemetry_policy_id: str
    resource_limit_profile_id: str
    trust_policy_id: str
    trust_policy_digest: str
    trust_policy_version: str
    trust_policy_expires_at: datetime
    required_assurance_level: str
    resulting_instance_state: Literal["enabled_runtime_trusted"]
    runtime_boundary_bound: Literal[True]
    runtime_trust_granted: Literal[True]
    eligible_for_secret_brokerage: Literal[True]
    runner_started: Literal[False]
    package_loaded: Literal[False]
    credential_resolution_authorized: Literal[False]
    credentials_resolved: Literal[False]
    target_connection_authorized: Literal[False]
    capability_invocation_authorized: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_application(
        cls, option: ConnectorRuntimeTrustOption
    ) -> ConnectorRuntimeTrustOptionData:
        result_flags = {
            "runtime_boundary_bound": True,
            "runtime_trust_granted": True,
            "eligible_for_secret_brokerage": True,
            "runner_started": False,
            "package_loaded": False,
            "credential_resolution_authorized": False,
            "credentials_resolved": False,
            "target_connection_authorized": False,
            "capability_invocation_authorized": False,
            "execution_authorized": False,
            "deployment_approved": False,
            "infrastructure_mutation_performed": False,
        }
        return cls.model_validate(
            {
                **{
                    field: getattr(option, field)
                    for field in cls.model_fields
                    if field not in result_flags and field != "required_assurance_level"
                },
                "required_assurance_level": option.required_assurance_level.value,
                **result_flags,
            }
        )


class ConnectorRuntimeTrustOptionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorRuntimeTrustOptionData, ...]
    meta: ResponseMeta
