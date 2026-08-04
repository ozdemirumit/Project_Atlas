from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas.api.bootstrap_state_schemas import BootstrapRunData, TrustProvisioningData
from atlas.api.deployment_configuration_schemas import DeploymentConfigurationOverlayInput
from atlas.api.schemas import ResponseMeta
from atlas.modules.platform.domain.bootstrap_state import BootstrapMutationResult
from atlas.modules.platform.domain.bootstrap_trust_provisioning import (
    BootstrapTrustPlan,
    TrustFileDisposition,
    TrustProvisioningState,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile

STABLE_ID_PATTERN = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST_PATTERN = r"^[a-f0-9]{64}$"


class BootstrapTrustPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-trust-plan-request.v1"]
    release_id: str = Field(pattern=STABLE_ID_PATTERN)
    profile: DeploymentProfile
    organization_id: str = Field(pattern=STABLE_ID_PATTERN)
    environment_id: str = Field(pattern=STABLE_ID_PATTERN)
    site_id: str = Field(pattern=STABLE_ID_PATTERN)
    configuration_digest: str = Field(pattern=DIGEST_PATTERN)
    overlay: DeploymentConfigurationOverlayInput


class BootstrapTrustAnchorData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor_id: str
    source_id: str
    purpose: str
    subject_summary: str
    sha256: str
    not_before: datetime
    not_after: datetime
    non_production_only: bool


class BootstrapWorkloadIdentityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity_id: str
    service_id: str
    instance_id: str
    owner_subject_id: str
    purpose: str
    environment_id: str
    audiences: list[str]
    secret_reference_ids: list[str]


class BootstrapTrustPlanData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    release_id: str
    profile: str
    organization_id: str
    environment_id: str
    site_id: str
    configuration_digest: str
    trust_plan_digest: str
    state: str
    result_code: str
    anchors: list[BootstrapTrustAnchorData]
    workload_identities: list[BootstrapWorkloadIdentityData]
    generated_at: datetime
    private_key_material_present: bool = False
    credential_material_present: bool = False
    infrastructure_mutation_authorized: bool = False
    ai_operation_authorized: bool = False

    @classmethod
    def from_domain(cls, plan: BootstrapTrustPlan) -> BootstrapTrustPlanData:
        return cls(
            schema_version=plan.schema_version,
            release_id=plan.release_id,
            profile=plan.profile.value,
            organization_id=plan.organization_id,
            environment_id=plan.environment_id,
            site_id=plan.site_id,
            configuration_digest=plan.configuration_digest,
            trust_plan_digest=plan.trust_plan_digest,
            state=plan.state.value,
            result_code=plan.result_code,
            anchors=[
                BootstrapTrustAnchorData(
                    anchor_id=item.anchor_id,
                    source_id=item.source_id,
                    purpose=item.purpose.value,
                    subject_summary=item.subject_summary,
                    sha256=item.sha256,
                    not_before=item.not_before,
                    not_after=item.not_after,
                    non_production_only=item.non_production_only,
                )
                for item in plan.anchors
            ],
            workload_identities=[
                BootstrapWorkloadIdentityData(
                    identity_id=item.identity_id,
                    service_id=item.service_id,
                    instance_id=item.instance_id,
                    owner_subject_id=item.owner_subject_id,
                    purpose=item.purpose,
                    environment_id=item.environment_id,
                    audiences=list(item.audiences),
                    secret_reference_ids=list(item.secret_reference_ids),
                )
                for item in plan.workload_identities
            ],
            generated_at=plan.generated_at,
        )


class BootstrapTrustPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapTrustPlanData
    meta: ResponseMeta


class BootstrapTrustProvisioningInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-trust-provisioning.v1"]
    organization_id: str = Field(pattern=STABLE_ID_PATTERN)
    environment_id: str = Field(pattern=STABLE_ID_PATTERN)
    site_id: str = Field(pattern=STABLE_ID_PATTERN)
    expected_version: int = Field(ge=1)
    plan_digest: str = Field(pattern=DIGEST_PATTERN)
    resume_key: str = Field(pattern=STABLE_ID_PATTERN)
    phase_id: Literal["phase.trust"]
    release_id: str = Field(pattern=STABLE_ID_PATTERN)
    profile: DeploymentProfile
    configuration_digest: str = Field(pattern=DIGEST_PATTERN)
    overlay: DeploymentConfigurationOverlayInput
    trust_schema_version: Literal["atlas.bootstrap-trust-plan.v1"]
    trust_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    justification: str = Field(min_length=12, max_length=500)

    @field_validator("justification")
    @classmethod
    def validate_justification(cls, value: str) -> str:
        if value != value.strip() or any(ord(character) < 32 for character in value):
            raise ValueError("justification must be trimmed single-line text")
        return value


class BootstrapTrustProvisioningData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: BootstrapRunData
    execution: TrustProvisioningData
    replayed: bool
    trust_storage_mutation_performed: bool
    private_key_mutation_performed: bool = False
    secret_value_mutation_performed: bool = False
    data_mutation_authorized: bool = False
    service_deployment_authorized: bool = False
    infrastructure_mutation_authorized: bool = False
    ai_operation_authorized: bool = False

    @classmethod
    def from_domain(cls, result: BootstrapMutationResult) -> BootstrapTrustProvisioningData:
        execution = result.trust_provisioning
        if execution is None:
            raise ValueError("trust provisioning response requires execution evidence")
        mutated = execution.state is TrustProvisioningState.COMPLETED and any(
            item.disposition is TrustFileDisposition.PUBLISHED for item in execution.evidence
        )
        return cls(
            run=BootstrapRunData.from_domain(result.record),
            execution=TrustProvisioningData.from_domain(execution),
            replayed=result.replayed,
            trust_storage_mutation_performed=mutated,
        )


class BootstrapTrustProvisioningResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapTrustProvisioningData
    meta: ResponseMeta
