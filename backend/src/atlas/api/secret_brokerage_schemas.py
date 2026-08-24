from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.application.secret_brokerage import (
    ConnectorSecretBrokerageOption,
)
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


class ConnectorSecretBrokerageInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_id: str
    source_runtime_trust_grant_id: str
    connector_id: str
    release_version: str
    instance_id: str
    display_name: str
    credential_class: str
    authentication_method: str
    privilege_class: str
    rotation_state: str
    revocation_state: str
    next_rotation_at: datetime
    runtime_profile_id: str
    brokerage_profile_id: str
    delivery_policy_id: str
    lease_policy_id: str
    maximum_lease_seconds: int
    revocation_policy_id: str
    brokerage_policy_id: str
    brokerage_policy_version: str
    authorization_version: int
    instance_state: Literal["enabled_secret_brokerage_governed"]
    authorized_by: str
    purpose: str
    authorized_at: datetime
    runtime_boundary_bound: Literal[True]
    runtime_trust_granted: Literal[True]
    eligible_for_secret_brokerage: Literal[True]
    secret_brokerage_governed: Literal[True]
    credential_resolution_authorized: Literal[True]
    eligible_for_runtime_activation: Literal[True]
    promotion_blocked: Literal[False]
    secret_lease_issued: Literal[False]
    credentials_resolved: Literal[False]
    runner_started: Literal[False]
    package_loaded: Literal[False]
    target_connection_authorized: Literal[False]
    capability_invocation_authorized: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_domain(
        cls, record: ConnectorSecretBrokerageAuthorizationRecord
    ) -> ConnectorSecretBrokerageInventoryData:
        return cls(**{field: getattr(record, field) for field in cls.model_fields})


class ConnectorSecretBrokerageInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorSecretBrokerageInventoryData, ...]
    meta: ResponseMeta


class ConnectorSecretBrokerageViewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorSecretBrokerageInventoryData
    meta: ResponseMeta


class ConnectorSecretBrokerageOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_runtime_trust_grant_id: str
    source_runtime_trust_digest: str
    package_digest: str
    brokerage_profile_id: str
    brokerage_profile_digest: str
    brokerage_profile_expires_at: datetime
    delivery_policy_id: str
    lease_policy_id: str
    maximum_lease_seconds: int
    revocation_policy_id: str
    brokerage_policy_id: str
    brokerage_policy_digest: str
    brokerage_policy_version: str
    brokerage_policy_expires_at: datetime
    required_assurance_level: str
    resulting_instance_state: Literal["enabled_secret_brokerage_governed"]
    secret_brokerage_governed: Literal[True]
    credential_resolution_authorized: Literal[True]
    eligible_for_runtime_activation: Literal[True]
    secret_lease_issued: Literal[False]
    credentials_resolved: Literal[False]
    runner_started: Literal[False]
    package_loaded: Literal[False]
    target_connection_authorized: Literal[False]
    capability_invocation_authorized: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_application(
        cls, option: ConnectorSecretBrokerageOption
    ) -> ConnectorSecretBrokerageOptionData:
        result_flags = {
            "secret_brokerage_governed": True,
            "credential_resolution_authorized": True,
            "eligible_for_runtime_activation": True,
            "secret_lease_issued": False,
            "credentials_resolved": False,
            "runner_started": False,
            "package_loaded": False,
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


class ConnectorSecretBrokerageOptionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorSecretBrokerageOptionData, ...]
    meta: ResponseMeta
