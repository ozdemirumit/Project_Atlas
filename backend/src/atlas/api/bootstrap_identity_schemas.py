from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas.api.bootstrap_state_schemas import BootstrapRunData, IdentityHandoffData
from atlas.api.deployment_configuration_schemas import DeploymentConfigurationOverlayInput
from atlas.api.schemas import ResponseMeta
from atlas.modules.platform.domain.bootstrap_identity_handoff import (
    BootstrapIdentityPlan,
    IdentityHandoffState,
    IdentityStateDisposition,
    IdentityTargetState,
)
from atlas.modules.platform.domain.bootstrap_state import BootstrapMutationResult
from atlas.modules.platform.domain.release_preflight import DeploymentProfile

STABLE_ID_PATTERN = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST_PATTERN = r"^[a-f0-9]{64}$"


class BootstrapIdentityPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-identity-plan-request.v1"]
    release_id: str = Field(pattern=STABLE_ID_PATTERN)
    profile: DeploymentProfile
    organization_id: str = Field(pattern=STABLE_ID_PATTERN)
    environment_id: str = Field(pattern=STABLE_ID_PATTERN)
    site_id: str = Field(pattern=STABLE_ID_PATTERN)
    configuration_digest: str = Field(pattern=DIGEST_PATTERN)
    overlay: DeploymentConfigurationOverlayInput
    trust_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    data_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    migration_artifact_digest: str = Field(pattern=DIGEST_PATTERN)
    service_plan_digest: str = Field(pattern=DIGEST_PATTERN)


class IdentityGroupMappingData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mapping_id: str
    directory_group_reference: str
    role_ids: list[str]


class BootstrapIdentityPlanData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    release_id: str
    profile: str
    organization_id: str
    environment_id: str
    site_id: str
    configuration_digest: str
    trust_plan_digest: str
    data_plan_digest: str
    service_plan_digest: str
    identity_plan_digest: str
    target_id: str
    target_kind: str
    target_state: str
    bootstrap_administrator_subject_id: str
    credential_verifier_reference_id: str
    credential_replacement_required: bool
    recovery_identity_id: str
    recovery_seal_required: bool
    provider_id: str
    provider_protocol: str
    pilot_subject_id: str
    group_mappings: list[IdentityGroupMappingData]
    state: str
    result_code: str
    generated_at: datetime
    credential_material_present: bool = False
    directory_mutation_authorized: bool = False
    provider_activation_authorized: bool = False
    account_mutation_authorized: bool = False
    session_or_token_mutation_authorized: bool = False
    infrastructure_mutation_authorized: bool = False
    ai_operation_authorized: bool = False

    @classmethod
    def from_domain(cls, plan: BootstrapIdentityPlan) -> BootstrapIdentityPlanData:
        return cls(
            **{
                "schema_version": plan.schema_version,
                "release_id": plan.release_id,
                "profile": plan.profile.value,
                "organization_id": plan.organization_id,
                "environment_id": plan.environment_id,
                "site_id": plan.site_id,
                "configuration_digest": plan.configuration_digest,
                "trust_plan_digest": plan.trust_plan_digest,
                "data_plan_digest": plan.data_plan_digest,
                "service_plan_digest": plan.service_plan_digest,
                "identity_plan_digest": plan.identity_plan_digest,
                "target_id": plan.target_id,
                "target_kind": plan.target_kind,
                "target_state": plan.target_state.value,
                "bootstrap_administrator_subject_id": plan.bootstrap_administrator_subject_id,
                "credential_verifier_reference_id": plan.credential_verifier_reference_id,
                "credential_replacement_required": plan.credential_replacement_required,
                "recovery_identity_id": plan.recovery_identity_id,
                "recovery_seal_required": plan.recovery_seal_required,
                "provider_id": plan.provider_id,
                "provider_protocol": plan.provider_protocol,
                "pilot_subject_id": plan.pilot_subject_id,
                "group_mappings": [
                    IdentityGroupMappingData(
                        mapping_id=item.mapping_id,
                        directory_group_reference=item.directory_group_reference,
                        role_ids=list(item.role_ids),
                    )
                    for item in plan.group_mappings
                ],
                "state": plan.state.value,
                "result_code": plan.result_code,
                "generated_at": plan.generated_at,
            }
        )


class BootstrapIdentityPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapIdentityPlanData
    meta: ResponseMeta


class BootstrapIdentityHandoffInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-identity-handoff.v1"]
    organization_id: str = Field(pattern=STABLE_ID_PATTERN)
    environment_id: str = Field(pattern=STABLE_ID_PATTERN)
    site_id: str = Field(pattern=STABLE_ID_PATTERN)
    expected_version: int = Field(ge=1)
    plan_digest: str = Field(pattern=DIGEST_PATTERN)
    resume_key: str = Field(pattern=STABLE_ID_PATTERN)
    phase_id: Literal["phase.identity"]
    release_id: str = Field(pattern=STABLE_ID_PATTERN)
    profile: DeploymentProfile
    configuration_digest: str = Field(pattern=DIGEST_PATTERN)
    overlay: DeploymentConfigurationOverlayInput
    trust_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    data_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    migration_artifact_digest: str = Field(pattern=DIGEST_PATTERN)
    service_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    identity_schema_version: Literal["atlas.bootstrap-identity-plan.v1"]
    identity_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    target_id: str = Field(pattern=STABLE_ID_PATTERN)
    expected_target_state: IdentityTargetState
    justification: str = Field(min_length=12, max_length=500)

    @field_validator("justification")
    @classmethod
    def validate_justification(cls, value: str) -> str:
        if value != value.strip() or any(ord(character) < 32 for character in value):
            raise ValueError("justification must be trimmed single-line text")
        return value


class BootstrapIdentityHandoffResultData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: BootstrapRunData
    execution: IdentityHandoffData
    replayed: bool
    synthetic_state_mutation_performed: bool
    credential_material_mutation_performed: bool = False
    directory_mutation_performed: bool = False
    provider_activation_performed: bool = False
    account_mutation_performed: bool = False
    session_or_token_mutation_performed: bool = False
    infrastructure_mutation_performed: bool = False
    ai_operation_performed: bool = False

    @classmethod
    def from_domain(cls, result: BootstrapMutationResult) -> BootstrapIdentityHandoffResultData:
        execution = result.identity_handoff
        if execution is None:
            raise ValueError("identity handoff response requires execution evidence")
        mutated = execution.state is IdentityHandoffState.COMPLETED and any(
            item.disposition is IdentityStateDisposition.PUBLISHED for item in execution.evidence
        )
        return cls(
            run=BootstrapRunData.from_domain(result.record),
            execution=IdentityHandoffData.from_domain(execution),
            replayed=result.replayed,
            synthetic_state_mutation_performed=mutated,
        )


class BootstrapIdentityHandoffResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapIdentityHandoffResultData
    meta: ResponseMeta
