from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.platform.domain.bootstrap_plan import BootstrapPlan, BootstrapPlanRequest
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class BootstrapPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-plan-request.v1"]
    release_id: str = Field(min_length=3, max_length=128)
    profile: DeploymentProfile
    organization_id: str = Field(min_length=3, max_length=128)
    environment_id: str = Field(min_length=3, max_length=128)
    site_id: str = Field(min_length=3, max_length=128)
    preflight_report_id: str = Field(min_length=3, max_length=128)
    manifest_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    preflight_state: Literal["passed", "failed", "warning", "unchecked"]
    configuration_preview_id: str = Field(min_length=3, max_length=128)
    configuration_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    configuration_state: Literal["passed", "failed"]

    def to_domain(self) -> BootstrapPlanRequest:
        return BootstrapPlanRequest(**self.model_dump())


class BootstrapPhaseData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phase_id: str
    sequence: int
    title: str
    dependencies: list[str]
    state: str
    resumable: bool
    input_references: list[str]
    stop_guidance: str


class BootstrapPlanData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str
    schema_version: str
    release_id: str
    profile: str
    organization_id: str
    environment_id: str
    site_id: str
    state: str
    plan_digest: str
    resume_key: str
    phases: list[BootstrapPhaseData]
    generated_at: datetime
    correlation_id: str
    mutation_authorized: bool
    execution_authorized: bool

    @classmethod
    def from_domain(cls, plan: BootstrapPlan) -> BootstrapPlanData:
        return cls(
            plan_id=plan.plan_id,
            schema_version=plan.schema_version,
            release_id=plan.release_id,
            profile=plan.profile.value,
            organization_id=plan.organization_id,
            environment_id=plan.environment_id,
            site_id=plan.site_id,
            state=plan.state.value,
            plan_digest=plan.plan_digest,
            resume_key=plan.resume_key,
            phases=[
                BootstrapPhaseData(
                    phase_id=item.phase_id,
                    sequence=item.sequence,
                    title=item.title,
                    dependencies=list(item.dependencies),
                    state=item.state.value,
                    resumable=item.resumable,
                    input_references=list(item.input_references),
                    stop_guidance=item.stop_guidance,
                )
                for item in plan.phases
            ],
            generated_at=plan.generated_at,
            correlation_id=plan.correlation_id,
            mutation_authorized=plan.mutation_authorized,
            execution_authorized=plan.execution_authorized,
        )


class BootstrapPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: BootstrapPlanData
    meta: ResponseMeta
