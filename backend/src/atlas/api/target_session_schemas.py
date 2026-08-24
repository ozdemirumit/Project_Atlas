from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.application.target_session import ConnectorTargetSessionOption
from atlas.modules.connectors.domain.target_session import (
    ConnectorTargetSessionVerificationRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorTargetSessionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.connector-target-session-input.v1"] = (
        "atlas.connector-target-session-input.v1"
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
    target_identity_digest: str
    protocol_classification: str
    tls_classification: str
    session_profile_digest: str
    session_policy_digest: str
    connectivity_check_results: tuple[TargetConnectivityCheckData, ...]
    instance_state: Literal["enabled_target_session_verified"]
    verified_at: datetime
    canonical_digest: str
    runtime_health_verified: Literal[True]
    secret_brokerage_governed: Literal[True]
    target_connection_authorized: Literal[True]
    target_connectivity_verified: Literal[True]
    target_identity_verified: Literal[True]
    read_only_session_verified: Literal[True]
    target_session_established: Literal[True]
    target_session_closed: Literal[True]
    delivery_channel_closed: Literal[True]
    lease_revocation_confirmed: Literal[True]
    eligible_for_capability_invocation_governance: Literal[True]
    target_connected: Literal[False]
    capability_invocation_authorized: Literal[False]
    capability_invoked: Literal[False]
    scheduled: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_domain(
        cls, record: ConnectorTargetSessionVerificationRecord
    ) -> ConnectorTargetSessionData:
        values = {field: getattr(record, field) for field in cls.model_fields}
        values["connectivity_check_results"] = tuple(
            TargetConnectivityCheckData(check_id=item.check_id, outcome=item.outcome)
            for item in record.connectivity_check_results
        )
        return cls(**values)


class ConnectorTargetSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorTargetSessionData
    meta: ResponseMeta


class ConnectorTargetSessionInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorTargetSessionData, ...]
    meta: ResponseMeta


class ConnectorTargetSessionOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_runtime_activation_id: str
    source_runtime_activation_digest: str
    package_digest: str
    session_profile_id: str
    session_profile_digest: str
    session_profile_expires_at: datetime
    expected_target_product: str
    protocol_classification: str
    connectivity_check_ids: tuple[str, ...]
    session_policy_id: str
    session_policy_digest: str
    session_policy_version: str
    session_policy_expires_at: datetime
    required_assurance_level: str
    resulting_instance_state: Literal["enabled_target_session_verified"]
    target_connection_authorized: Literal[True]
    target_connectivity_verified: Literal[True]
    target_identity_verified: Literal[True]
    read_only_session_verified: Literal[True]
    target_session_closed: Literal[True]
    delivery_channel_closed: Literal[True]
    lease_revocation_confirmed: Literal[True]
    eligible_for_capability_invocation_governance: Literal[True]
    target_connected: Literal[False]
    capability_invocation_authorized: Literal[False]
    capability_invoked: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_application(
        cls, option: ConnectorTargetSessionOption
    ) -> ConnectorTargetSessionOptionData:
        return cls.model_validate(
            {
                **{
                    field: getattr(option, field)
                    for field in ConnectorTargetSessionOption.__dataclass_fields__
                    if field != "required_assurance_level"
                },
                "required_assurance_level": option.required_assurance_level.value,
                "resulting_instance_state": "enabled_target_session_verified",
                "target_connection_authorized": True,
                "target_connectivity_verified": True,
                "target_identity_verified": True,
                "read_only_session_verified": True,
                "target_session_closed": True,
                "delivery_channel_closed": True,
                "lease_revocation_confirmed": True,
                "eligible_for_capability_invocation_governance": True,
                "target_connected": False,
                "capability_invocation_authorized": False,
                "capability_invoked": False,
                "execution_authorized": False,
                "deployment_approved": False,
                "infrastructure_mutation_performed": False,
            }
        )


class ConnectorTargetSessionOptionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorTargetSessionOptionData, ...]
    meta: ResponseMeta
