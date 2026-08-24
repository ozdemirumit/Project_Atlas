from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.application.runtime_activation import (
    ConnectorRuntimeActivationOption,
)
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


class ConnectorRuntimeActivationInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activation_id: str
    source_brokerage_authorization_id: str
    connector_id: str
    release_version: str
    instance_id: str
    display_name: str
    activation_profile_id: str
    activation_policy_id: str
    activation_policy_version: str
    activation_adapter_id: str
    health_probe_results: tuple[RuntimeHealthProbeData, ...]
    instance_state: Literal["enabled_runtime_healthy"]
    activated_by: str
    purpose: str
    activated_at: datetime
    healthy_at: datetime
    runtime_boundary_bound: Literal[True]
    runtime_trust_granted: Literal[True]
    secret_brokerage_governed: Literal[True]
    credential_resolution_authorized: Literal[True]
    secret_lease_issued: Literal[True]
    credentials_resolved: Literal[True]
    runner_started: Literal[True]
    package_loaded: Literal[True]
    runtime_health_verified: Literal[True]
    lease_delivery_completed: Literal[True]
    delivery_channel_closed: Literal[True]
    lease_revocation_confirmed: Literal[True]
    eligible_for_target_session_authorization: Literal[True]
    target_connected: Literal[False]
    target_connection_authorized: Literal[False]
    capability_invocation_authorized: Literal[False]
    capability_invoked: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_domain(
        cls, record: ConnectorRuntimeActivationRecord
    ) -> ConnectorRuntimeActivationInventoryData:
        values = {field: getattr(record, field) for field in cls.model_fields}
        values["health_probe_results"] = tuple(
            RuntimeHealthProbeData(probe_id=item.probe_id, outcome=item.outcome)
            for item in record.health_probe_results
        )
        return cls(**values)


class ConnectorRuntimeActivationInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorRuntimeActivationInventoryData, ...]
    meta: ResponseMeta


class ConnectorRuntimeActivationViewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorRuntimeActivationInventoryData
    meta: ResponseMeta


class ConnectorRuntimeActivationOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_brokerage_authorization_id: str
    source_brokerage_authorization_digest: str
    package_digest: str
    activation_profile_id: str
    activation_profile_digest: str
    activation_profile_expires_at: datetime
    health_probe_ids: tuple[str, ...]
    activation_policy_id: str
    activation_policy_digest: str
    activation_policy_version: str
    activation_policy_expires_at: datetime
    required_assurance_level: str
    resulting_instance_state: Literal["enabled_runtime_healthy"]
    secret_lease_issued: Literal[True]
    credentials_resolved: Literal[True]
    runner_started: Literal[True]
    package_loaded: Literal[True]
    runtime_health_verified: Literal[True]
    delivery_channel_closed: Literal[True]
    lease_revocation_confirmed: Literal[True]
    eligible_for_target_session_authorization: Literal[True]
    target_connected: Literal[False]
    target_connection_authorized: Literal[False]
    capability_invocation_authorized: Literal[False]
    capability_invoked: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_application(
        cls, option: ConnectorRuntimeActivationOption
    ) -> ConnectorRuntimeActivationOptionData:
        return cls.model_validate(
            {
                **{
                    field: getattr(option, field)
                    for field in ConnectorRuntimeActivationOption.__dataclass_fields__
                    if field != "required_assurance_level"
                },
                "required_assurance_level": option.required_assurance_level.value,
                "resulting_instance_state": "enabled_runtime_healthy",
                "secret_lease_issued": True,
                "credentials_resolved": True,
                "runner_started": True,
                "package_loaded": True,
                "runtime_health_verified": True,
                "delivery_channel_closed": True,
                "lease_revocation_confirmed": True,
                "eligible_for_target_session_authorization": True,
                "target_connected": False,
                "target_connection_authorized": False,
                "capability_invocation_authorized": False,
                "capability_invoked": False,
                "execution_authorized": False,
                "deployment_approved": False,
                "infrastructure_mutation_performed": False,
            }
        )


class ConnectorRuntimeActivationOptionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorRuntimeActivationOptionData, ...]
    meta: ResponseMeta
