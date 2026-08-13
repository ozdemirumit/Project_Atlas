from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.core.classification import DataClassification
from atlas.modules.itsm.domain.models import (
    ItsmAllowedOperation,
    ItsmCheckState,
    ItsmIntegrationProfile,
    ItsmProfileLifecycle,
    ItsmProviderFamily,
    ItsmReadinessState,
    ItsmWriteSemantics,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
PROFILE_KEY = r"^[a-z][a-z0-9_.:-]{2,127}$"
PROVIDER_FIELD = r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ItsmFieldMappingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_field: str
    provider_field: str = Field(pattern=PROVIDER_FIELD)
    write_semantics: ItsmWriteSemantics


class CreateItsmIntegrationProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.itsm-integration-profile-create-input.v1", pattern=STABLE_ID
    )
    profile_key: str = Field(pattern=PROFILE_KEY)
    display_name: str = Field(min_length=3, max_length=160)
    provider_family: ItsmProviderFamily
    instance_reference: str = Field(pattern=STABLE_ID)
    owner_id: str = Field(pattern=STABLE_ID)
    purpose: str = Field(min_length=20, max_length=1000)
    endpoint_origin: str = Field(min_length=9, max_length=2048)
    trust_boundary_reference: str = Field(pattern=STABLE_ID)
    secret_reference_id: str = Field(pattern=r"^secret\.[a-z0-9_.:-]{2,120}$")
    classification_ceiling: DataClassification
    allowed_operations: list[ItsmAllowedOperation] = Field(min_length=1, max_length=2)
    mapping_version: int = Field(ge=1)
    field_mappings: list[ItsmFieldMappingInput] = Field(min_length=1, max_length=5)
    sandbox_validation_reference: str | None = Field(default=None, pattern=STABLE_ID)
    sandbox_validation_digest: str | None = Field(default=None, pattern=DIGEST)
    audit_profile_id: str = Field(pattern=STABLE_ID)
    acknowledged_configuration_only: bool


class RetireItsmIntegrationProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.itsm-integration-profile-retirement-input.v1", pattern=STABLE_ID
    )
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=20, max_length=1000)
    acknowledged_history_preserved_and_dispatch_absent: bool


class ItsmFieldMappingData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    source_field: str
    provider_field: str
    write_semantics: ItsmWriteSemantics


class ItsmReadinessCheckData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    check_id: str
    state: ItsmCheckState
    reason_code: str


class ItsmReadinessData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    state: ItsmReadinessState
    checks: list[ItsmReadinessCheckData]
    assessed_at: datetime
    canonical_digest: str
    dispatch_authorized: bool
    external_record_mutation_authorized: bool
    workflow_approved: bool
    execution_authorized: bool


class ItsmIntegrationProfileData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    site_id: str
    profile_key: str
    display_name: str
    provider_family: ItsmProviderFamily
    instance_reference: str
    owner_id: str
    purpose: str
    endpoint_origin: str
    trust_boundary_reference: str
    credential_reference_configured: bool
    classification_ceiling: DataClassification
    allowed_operations: list[ItsmAllowedOperation]
    mapping_version: int
    field_mappings: list[ItsmFieldMappingData]
    sandbox_validation_reference: str | None
    sandbox_validation_digest: str | None
    audit_profile_id: str
    lifecycle: ItsmProfileLifecycle
    readiness: ItsmReadinessData
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime
    retired_by: str | None
    retired_at: datetime | None
    retirement_reason: str | None
    canonical_digest: str
    reused: bool

    @classmethod
    def from_domain(cls, record: ItsmIntegrationProfile) -> ItsmIntegrationProfileData:
        return cls(
            **{
                field: getattr(record, field)
                for field in cls.model_fields
                if field != "credential_reference_configured"
            },
            credential_reference_configured=bool(record.secret_reference_id),
        )


class ItsmIntegrationProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ItsmIntegrationProfileData
    meta: ResponseMeta


class ItsmIntegrationProfileInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profiles: list[ItsmIntegrationProfileData]
    durable: bool
    truncated: bool


class ItsmIntegrationProfileInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ItsmIntegrationProfileInventoryData
    meta: ResponseMeta
