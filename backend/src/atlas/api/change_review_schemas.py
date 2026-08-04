from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.change_review.domain.packet import (
    UpgradeChangeReviewPacket,
    UpgradeChangeReviewPreview,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ChangeReviewPreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.upgrade-change-review-preview-request.v1", pattern=STABLE_ID
    )
    source_run_id: str = Field(pattern=STABLE_ID)
    source_run_version: int = Field(ge=1)
    backup_id: str = Field(pattern=STABLE_ID)
    restore_validation_id: str = Field(pattern=STABLE_ID)
    target_release_id: str = Field(pattern=STABLE_ID)
    plan_id: str = Field(pattern=STABLE_ID)
    plan_digest: str = Field(pattern=DIGEST)
    simulation_id: str = Field(pattern=STABLE_ID)
    simulation_digest: str = Field(pattern=DIGEST)


class ChangeReviewPreviewData(BaseModel):
    preview_id: str
    schema_version: str
    source_run_id: str
    source_run_version: int
    plan_id: str
    plan_digest: str
    simulation_id: str
    simulation_digest: str
    source_release_id: str
    source_release_version: str
    target_release_id: str
    target_release_version: str
    backup_id: str
    restore_validation_id: str
    risk_class: str
    change_class: str
    impacted_service_ids: list[str]
    migration_step_ids: list[str]
    abort_criterion_ids: list[str]
    rollback_step_ids: list[str]
    post_verification_check_ids: list[str]
    assumption_ids: list[str]
    unknown_ids: list[str]
    residual_risk_ids: list[str]
    owner_role_ids: list[str]
    evidence_digests: list[str]
    estimated_downtime_min_minutes: int
    estimated_downtime_max_minutes: int
    rollback_window_minutes: int
    state: str
    preview_digest: str
    generated_at: datetime
    expires_at: datetime
    approval_granted: bool
    execution_authorized: bool
    dispatch_authorized: bool
    infrastructure_mutation_performed: bool

    @classmethod
    def from_domain(cls, item: UpgradeChangeReviewPreview) -> ChangeReviewPreviewData:
        list_fields = {
            "impacted_service_ids",
            "migration_step_ids",
            "abort_criterion_ids",
            "rollback_step_ids",
            "post_verification_check_ids",
            "assumption_ids",
            "unknown_ids",
            "residual_risk_ids",
            "owner_role_ids",
            "evidence_digests",
        }
        return cls.model_validate(
            {
                **{
                    field: getattr(item, field)
                    for field in cls.model_fields
                    if field not in list_fields | {"state"}
                },
                **{field: list(getattr(item, field)) for field in list_fields},
                "state": item.state.value,
            }
        )


class ChangeReviewPreviewResponse(BaseModel):
    data: ChangeReviewPreviewData
    meta: ResponseMeta


class ChangeReviewCreateInput(ChangeReviewPreviewInput):
    schema_version: str = Field(
        default="atlas.upgrade-change-review-create-request.v1", pattern=STABLE_ID
    )
    preview_id: str = Field(pattern=STABLE_ID)
    preview_digest: str = Field(pattern=DIGEST)
    preview_expires_at: datetime
    proposed_window_start: datetime
    proposed_window_end: datetime
    justification: str = Field(min_length=12, max_length=500)
    confirmed: bool
    acknowledged_no_authority: bool


class ChangeReviewPacketData(BaseModel):
    packet_id: str
    schema_version: str
    state: str
    source_run_id: str
    source_run_version: int
    preview_id: str
    preview_digest: str
    plan_id: str
    plan_digest: str
    simulation_id: str
    simulation_digest: str
    backup_id: str
    restore_validation_id: str
    risk_class: str
    change_class: str
    impacted_service_ids: list[str]
    migration_step_ids: list[str]
    abort_criterion_ids: list[str]
    rollback_step_ids: list[str]
    post_verification_check_ids: list[str]
    assumption_ids: list[str]
    unknown_ids: list[str]
    residual_risk_ids: list[str]
    owner_role_ids: list[str]
    evidence_digests: list[str]
    proposed_window_start: datetime
    proposed_window_end: datetime
    estimated_downtime_min_minutes: int
    estimated_downtime_max_minutes: int
    rollback_window_minutes: int
    itsm_draft_id: str
    itsm_draft_title: str
    itsm_draft_digest: str
    packet_digest: str
    created_at: datetime
    reused: bool
    approval_granted: bool
    execution_authorized: bool
    itsm_dispatched: bool
    notification_sent: bool
    workflow_executed: bool
    infrastructure_mutation_performed: bool

    @classmethod
    def from_domain(cls, item: UpgradeChangeReviewPacket) -> ChangeReviewPacketData:
        list_fields = {
            "impacted_service_ids",
            "migration_step_ids",
            "abort_criterion_ids",
            "rollback_step_ids",
            "post_verification_check_ids",
            "assumption_ids",
            "unknown_ids",
            "residual_risk_ids",
            "owner_role_ids",
            "evidence_digests",
        }
        return cls.model_validate(
            {
                **{
                    field: getattr(item, field)
                    for field in cls.model_fields
                    if field not in list_fields | {"state"}
                },
                **{field: list(getattr(item, field)) for field in list_fields},
                "state": item.state.value,
            }
        )


class ChangeReviewPacketResponse(BaseModel):
    data: ChangeReviewPacketData
    meta: ResponseMeta
