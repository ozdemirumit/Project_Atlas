from __future__ import annotations

from datetime import datetime
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.application.bounded_invocation import (
    ConnectorBoundedInvocationOption,
)
from atlas.modules.connectors.domain.bounded_invocation import (
    ConnectorBoundedInvocationRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorBoundedInvocationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.connector-bounded-invocation-input.v1"] = (
        "atlas.connector-bounded-invocation-input.v1"
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
    source_authorization_id: str
    source_authorization_digest: str
    package_digest: str
    capability_id: str
    capability_class: Literal["C0", "C1"]
    required_permission: str
    output_schema_digest: str
    result_policy_digest: str
    invocation_policy_id: str
    invocation_policy_digest: str
    invocation_policy_version: str
    normalized_redacted_result_digest: str
    observation_count: int
    output_bytes: int
    instance_state: Literal["enabled_bounded_capability_invocation_completed"]
    started_at: datetime
    completed_at: datetime
    canonical_digest: str
    authorization_consumed: Literal[True]
    target_connection_opened: Literal[True]
    capability_invoked: Literal[True]
    result_received: Literal[True]
    result_validated: Literal[True]
    result_redacted: Literal[True]
    target_session_closed: Literal[True]
    delivery_channel_closed: Literal[True]
    lease_revocation_confirmed: Literal[True]
    target_connected: Literal[False]
    reusable_session_available: Literal[False]
    scheduled: Literal[False]
    evidence_ingested: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]
    reused: bool

    @classmethod
    def from_domain(
        cls, record: ConnectorBoundedInvocationRecord
    ) -> ConnectorBoundedInvocationData:
        return cls(**{field: getattr(record, field) for field in cls.model_fields})


class ConnectorBoundedInvocationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorBoundedInvocationData
    meta: ResponseMeta


class ConnectorBoundedInvocationInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorBoundedInvocationData, ...]
    meta: ResponseMeta


class ConnectorBoundedInvocationOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_authorization_id: str
    source_authorization_digest: str
    package_digest: str
    capability_id: str
    capability_class: Literal["C0", "C1"]
    required_permission: str
    invocation_policy_id: str
    invocation_policy_digest: str
    invocation_policy_version: str
    invocation_policy_expires_at: datetime
    required_assurance_level: Literal["single_factor", "multi_factor", "hardware_backed"]
    maximum_timeout_seconds: int
    maximum_output_bytes: int
    maximum_observations: int
    resulting_instance_state: Literal["enabled_bounded_capability_invocation_completed"]
    irreversible_consumption_required: Literal[True]
    automatic_retry_allowed: Literal[False]
    target_connected: Literal[False]
    reusable_session_available: Literal[False]
    scheduled: Literal[False]
    evidence_ingested: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_application(
        cls, option: ConnectorBoundedInvocationOption
    ) -> ConnectorBoundedInvocationOptionData:
        values = {
            field: getattr(option, field)
            for field in ConnectorBoundedInvocationOption.__dataclass_fields__
            if field != "required_assurance_level"
        }
        return cls(
            **values,
            required_assurance_level=cast(
                Literal["single_factor", "multi_factor", "hardware_backed"],
                option.required_assurance_level.value,
            ),
            resulting_instance_state="enabled_bounded_capability_invocation_completed",
            irreversible_consumption_required=True,
            automatic_retry_allowed=False,
            target_connected=False,
            reusable_session_available=False,
            scheduled=False,
            evidence_ingested=False,
            execution_authorized=False,
            deployment_approved=False,
            infrastructure_mutation_performed=False,
        )


class ConnectorBoundedInvocationOptionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorBoundedInvocationOptionData, ...]
    meta: ResponseMeta
