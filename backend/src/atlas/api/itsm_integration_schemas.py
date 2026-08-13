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
    ItsmSandboxConformanceAssessment,
    ItsmSandboxConformanceState,
    ItsmSandboxOnboardingReadiness,
    ItsmSandboxOnboardingRequirementState,
    ItsmSandboxOnboardingState,
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


class CreateItsmSandboxConformanceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.itsm-sandbox-conformance-input.v1", pattern=STABLE_ID
    )
    expected_profile_version: int = Field(ge=1)
    acknowledged_diagnostic_only_and_no_dispatch: bool


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


class ItsmSandboxConformanceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    site_id: str
    profile_id: str
    profile_version: int
    profile_digest: str
    mapping_version: int
    assessed_by: str
    adapter_id: str
    adapter_version: str
    adapter_production_eligible: bool
    diagnostic_contract_version: str
    challenge_digest: str
    observed_at: datetime
    valid_until: datetime
    state: ItsmSandboxConformanceState
    reason_codes: list[str]
    canonical_digest: str
    diagnostic_only: bool
    sandbox_conformant: bool
    production_ready: bool
    dispatch_authorized: bool
    external_record_mutation_authorized: bool
    workflow_approved: bool
    execution_authorized: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, assessment: ItsmSandboxConformanceAssessment
    ) -> ItsmSandboxConformanceData:
        return cls(**{field: getattr(assessment, field) for field in cls.model_fields})


class ItsmSandboxConformanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ItsmSandboxConformanceData
    meta: ResponseMeta


class ItsmSandboxOnboardingRequirementData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    requirement_id: str
    state: ItsmSandboxOnboardingRequirementState
    reason_code: str


class ItsmSandboxOnboardingReadinessData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    site_id: str
    profile_id: str
    profile_version: int
    profile_digest: str
    mapping_version: int
    conformance_assessment_id: str | None
    conformance_assessment_digest: str | None
    adapter_id: str | None
    adapter_version: str | None
    policy_id: str
    policy_version: int
    policy_digest: str
    policy_issuer: str
    policy_expires_at: datetime
    assessed_at: datetime
    evidence_observed_at: datetime | None
    evidence_valid_until: datetime | None
    state: ItsmSandboxOnboardingState
    requirements: list[ItsmSandboxOnboardingRequirementData]
    canonical_digest: str
    sandbox_onboarding_ready: bool
    production_ready: bool
    dispatch_authorized: bool
    external_record_mutation_authorized: bool
    workflow_approved: bool
    execution_authorized: bool
    infrastructure_mutation_performed: bool

    @classmethod
    def from_domain(
        cls, readiness: ItsmSandboxOnboardingReadiness
    ) -> ItsmSandboxOnboardingReadinessData:
        return cls(**{field: getattr(readiness, field) for field in cls.model_fields})


class ItsmSandboxOnboardingReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ItsmSandboxOnboardingReadinessData
    meta: ResponseMeta
