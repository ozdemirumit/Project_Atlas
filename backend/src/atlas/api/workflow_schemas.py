from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.workflows.domain import WorkflowDefinition, WorkflowRunPlan

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,239}$"


class CreateWorkflowPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.workflow-run-plan-create-input.v1"]
    definition_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    definition_version: int = Field(ge=1)
    target_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    target_type: Literal["storage"]
    inputs: dict[str, object]
    acknowledged_planning_only_no_execution_authority: Literal[True]


class WorkflowStepDefinitionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    ordinal: int
    title: str
    kind: str
    capability_class: str
    timeout_seconds: int
    depends_on: list[str]


class WorkflowDefinitionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    definition_id: str
    version: int
    title: str
    purpose: str
    input_schema_version: str
    definition_digest: str
    steps: list[WorkflowStepDefinitionData]

    @classmethod
    def from_domain(cls, definition: WorkflowDefinition) -> WorkflowDefinitionData:
        return cls(
            definition_id=definition.definition_id,
            version=definition.version,
            title=definition.title,
            purpose=definition.purpose,
            input_schema_version=definition.input_schema_version,
            definition_digest=definition.definition_digest,
            steps=[
                WorkflowStepDefinitionData(
                    step_id=step.step_id,
                    ordinal=step.ordinal,
                    title=step.title,
                    kind=step.kind.value,
                    capability_class=step.capability_class.value,
                    timeout_seconds=step.timeout_seconds,
                    depends_on=list(step.depends_on),
                )
                for step in definition.steps
            ],
        )


class WorkflowPlanStepData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    ordinal: int
    kind: str
    capability_class: str
    state: Literal["not_started"]


class WorkflowPlanAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    worker_dispatch_authorized: Literal[False]
    connector_invocation_authorized: Literal[False]
    approval_creation_authorized: Literal[False]
    signal_delivery_authorized: Literal[False]
    retry_authorized: Literal[False]
    itsm_mutation_authorized: Literal[False]
    runbook_execution_authorized: Literal[False]
    infrastructure_change_authorized: Literal[False]


class WorkflowScopeData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: str
    environment_id: str
    site_id: str


class WorkflowRunPlanData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    definition_id: str
    definition_version: int
    definition_digest: str
    scope: WorkflowScopeData
    target_id: str
    target_type: Literal["storage"]
    canonical_input_digest: str
    creator_subject_id: str
    created_at: datetime
    state: Literal["planned"]
    steps: list[WorkflowPlanStepData]
    durable: bool
    authority: WorkflowPlanAuthorityData
    safety_notice: str
    canonical_digest: str

    @classmethod
    def from_domain(cls, plan: WorkflowRunPlan) -> WorkflowRunPlanData:
        return cls.model_validate(
            plan.digest_payload() | {"canonical_digest": plan.canonical_digest}
        )


class WorkflowDefinitionInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    definitions: list[WorkflowDefinitionData]


class WorkflowPlanInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plans: list[WorkflowRunPlanData]
    durable: bool
    truncated: bool


class WorkflowDefinitionInventoryResponse(BaseModel):
    data: WorkflowDefinitionInventoryData
    meta: ResponseMeta


class WorkflowPlanInventoryResponse(BaseModel):
    data: WorkflowPlanInventoryData
    meta: ResponseMeta


class WorkflowRunPlanResponse(BaseModel):
    data: WorkflowRunPlanData
    meta: ResponseMeta
