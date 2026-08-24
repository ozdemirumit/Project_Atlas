from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.application.invocation_authorization import (
    ConnectorInvocationAuthorizationOption,
)
from atlas.modules.connectors.domain.invocation_authorization import (
    ConnectorInvocationAuthorizationRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorInvocationAuthorizationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.connector-invocation-authorization-input.v1"] = (
        "atlas.connector-invocation-authorization-input.v1"
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
    capability_id: str
    capability_class: Literal["C0", "C1"]
    invocation_profile_digest: str
    input_envelope_digest: str
    authorization_policy_digest: str
    instance_state: Literal["enabled_capability_invocation_governed"]
    authorized_at: datetime
    expires_at: datetime
    canonical_digest: str
    target_session_verified: Literal[True]
    capability_enabled: Literal[True]
    capability_permission_verified: Literal[True]
    capability_invocation_authorized: Literal[True]
    eligible_for_bounded_capability_invocation: Literal[True]
    single_use: Literal[True]
    renewable: Literal[False]
    consumed: Literal[False]
    target_connected: Literal[False]
    capability_invoked: Literal[False]
    scheduled: Literal[False]
    result_received: Literal[False]
    result_validated: Literal[False]
    evidence_ingested: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_domain(
        cls, record: ConnectorInvocationAuthorizationRecord
    ) -> ConnectorInvocationAuthorizationData:
        return cls(**{field: getattr(record, field) for field in cls.model_fields})


class ConnectorInvocationAuthorizationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorInvocationAuthorizationData
    meta: ResponseMeta


class ConnectorInvocationAuthorizationInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorInvocationAuthorizationData, ...]
    meta: ResponseMeta


class ConnectorInvocationAuthorizationOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_target_session_verification_id: str
    source_target_session_digest: str
    package_digest: str
    capability_id: str
    capability_class: Literal["C0", "C1"]
    required_permission: str
    invocation_profile_id: str
    invocation_profile_digest: str
    invocation_profile_expires_at: datetime
    input_envelope_id: str
    input_envelope_digest: str
    input_envelope_expires_at: datetime
    input_envelope_field_count: int
    authorization_policy_id: str
    authorization_policy_digest: str
    authorization_policy_version: str
    authorization_policy_expires_at: datetime
    required_assurance_level: Literal["single_factor", "multi_factor", "hardware_backed"]
    maximum_timeout_seconds: int
    maximum_output_bytes: int
    resulting_instance_state: Literal["enabled_capability_invocation_governed"]
    capability_invocation_authorized: Literal[True]
    eligible_for_bounded_capability_invocation: Literal[True]
    single_use: Literal[True]
    renewable: Literal[False]
    consumed: Literal[False]
    target_connected: Literal[False]
    capability_invoked: Literal[False]
    scheduled: Literal[False]
    result_received: Literal[False]
    result_validated: Literal[False]
    evidence_ingested: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_application(
        cls, option: ConnectorInvocationAuthorizationOption
    ) -> ConnectorInvocationAuthorizationOptionData:
        values = {
            field: getattr(option, field)
            for field in ConnectorInvocationAuthorizationOption.__dataclass_fields__
            if field != "required_assurance_level"
        }
        return cls(
            **values,
            required_assurance_level=option.required_assurance_level.value,
            resulting_instance_state="enabled_capability_invocation_governed",
            capability_invocation_authorized=True,
            eligible_for_bounded_capability_invocation=True,
            single_use=True,
            renewable=False,
            consumed=False,
            target_connected=False,
            capability_invoked=False,
            scheduled=False,
            result_received=False,
            result_validated=False,
            evidence_ingested=False,
            execution_authorized=False,
            deployment_approved=False,
            infrastructure_mutation_performed=False,
        )


class ConnectorInvocationAuthorizationOptionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorInvocationAuthorizationOptionData, ...]
    meta: ResponseMeta
