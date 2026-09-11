from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.operations.domain.models import OperationResource, OperationState


class OperationResourceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str
    operation_type: str
    owner_subject_id: str
    organization_id: str
    environment_id: str
    state: OperationState
    progress_summary: str
    created_at: datetime
    started_at: datetime | None
    updated_at: datetime
    deadline_at: datetime | None
    expires_at: datetime | None
    input_artifact_reference: str
    workflow_run_reference: str | None
    correlation_id: str
    current_step: str
    result_reference: str | None
    partial_result_reference: str | None
    error_reference: str | None
    evidence_references: tuple[str, ...]
    cancellation_eligible: bool
    cancellation_reason: str | None
    required_human_task_reference: str | None

    @classmethod
    def from_domain(cls, resource: OperationResource) -> OperationResourceData:
        return cls.model_validate(resource, from_attributes=True)


class OperationResourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationResourceData
    meta: ResponseMeta


class OperationCancellationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)
