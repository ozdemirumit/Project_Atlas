from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.application.credential_assignment import (
    ConnectorCredentialAssignmentOption,
)
from atlas.modules.connectors.domain.credential_assignment import (
    ConnectorCredentialAssignmentRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorCredentialAssignmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-credential-assignment-input.v1", pattern=STABLE_ID
    )
    source_target_binding_id: str = Field(pattern=STABLE_ID)
    source_target_binding_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    credential_profile_id: str = Field(pattern=STABLE_ID)
    credential_profile_digest: str = Field(pattern=DIGEST)
    credential_policy_id: str = Field(pattern=STABLE_ID)
    credential_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_assignment_grants_no_secret_access_enablement_or_runtime_authority: bool


class ConnectorCredentialAssignmentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment_id: str
    schema_version: str
    version: int
    source_target_binding_id: str
    source_target_binding_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    connector_id: str
    release_version: str
    manifest_digest: str
    instance_id: str
    instance_key: str
    display_name: str
    owner_id: str
    target_profile_id: str
    target_profile_digest: str
    site_id: str
    target_type: str
    target_product: str
    credential_profile_id: str
    credential_profile_digest: str
    credential_class: str
    authentication_method: str
    vendor_role: str
    privilege_class: str
    rotation_state: str
    revocation_state: str
    next_rotation_at: datetime
    credential_policy_id: str
    credential_policy_digest: str
    credential_policy_version: str
    assignment_version: int
    instance_state: str
    assigned_by: str
    purpose: str
    assigned_at: datetime
    canonical_digest: str
    package_installed: bool
    instance_created: bool
    target_configured: bool
    eligible_for_credential_governance: bool
    credential_references_assigned: bool
    eligible_for_configuration_validation: bool
    promotion_blocked: bool
    credentials_resolved: bool
    connector_enabled: bool
    runtime_trust_granted: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, record: ConnectorCredentialAssignmentRecord
    ) -> ConnectorCredentialAssignmentData:
        return cls(**{field: getattr(record, field) for field in cls.model_fields})


class ConnectorCredentialAssignmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorCredentialAssignmentData
    meta: ResponseMeta


class ConnectorCredentialAssignmentInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment_id: str
    source_target_binding_id: str
    connector_id: str
    release_version: str
    instance_id: str
    display_name: str
    credential_profile_id: str
    credential_profile_digest: str
    credential_class: str
    authentication_method: str
    vendor_role: str
    privilege_class: str
    rotation_state: str
    revocation_state: str
    next_rotation_at: datetime
    credential_policy_id: str
    credential_policy_digest: str
    credential_policy_version: str
    instance_state: Literal["disabled_credentials_assigned"]
    assigned_by: str
    purpose: str
    assigned_at: datetime
    credential_references_assigned: Literal[True]
    eligible_for_configuration_validation: Literal[True]
    credentials_resolved: Literal[False]
    connector_enabled: Literal[False]
    runtime_trust_granted: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_domain(
        cls, record: ConnectorCredentialAssignmentRecord
    ) -> ConnectorCredentialAssignmentInventoryData:
        return cls(**{field: getattr(record, field) for field in cls.model_fields})


class ConnectorCredentialAssignmentInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorCredentialAssignmentInventoryData, ...]
    meta: ResponseMeta


class ConnectorCredentialAssignmentOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_target_binding_id: str
    credential_profile_id: str
    credential_profile_digest: str
    credential_class: str
    authentication_method: str
    vendor_role: str
    privilege_class: str
    rotation_state: str
    revocation_state: str
    next_rotation_at: datetime
    credential_profile_expires_at: datetime
    credential_policy_id: str
    credential_policy_digest: str
    credential_policy_version: str
    credential_policy_expires_at: datetime
    required_assurance_level: str
    resulting_instance_state: Literal["disabled_credentials_assigned"]
    resulting_credential_references_assigned: Literal[True]
    eligible_for_configuration_validation: Literal[True]
    credentials_resolved: Literal[False]
    connector_enabled: Literal[False]
    runtime_trust_granted: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_application(
        cls, option: ConnectorCredentialAssignmentOption
    ) -> ConnectorCredentialAssignmentOptionData:
        return cls(
            **{
                field: getattr(option, field)
                for field in cls.model_fields
                if field
                not in {
                    "required_assurance_level",
                    "resulting_credential_references_assigned",
                    "eligible_for_configuration_validation",
                    "credentials_resolved",
                    "connector_enabled",
                    "runtime_trust_granted",
                    "execution_authorized",
                    "infrastructure_mutation_performed",
                }
            },
            required_assurance_level=option.required_assurance_level.value,
            resulting_credential_references_assigned=True,
            eligible_for_configuration_validation=True,
            credentials_resolved=False,
            connector_enabled=False,
            runtime_trust_granted=False,
            execution_authorized=False,
            infrastructure_mutation_performed=False,
        )


class ConnectorCredentialAssignmentOptionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorCredentialAssignmentOptionData, ...]
    meta: ResponseMeta
