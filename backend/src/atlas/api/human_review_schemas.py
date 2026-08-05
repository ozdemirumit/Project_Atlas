from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.change_review.domain.completion_receipt import HumanReviewCompletionReceipt
from atlas.modules.change_review.domain.human_review import UpgradeChangeHumanReview

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class HumanReviewCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.upgrade-change-human-review-create-request.v1", pattern=STABLE_ID
    )
    packet_id: str = Field(pattern=STABLE_ID)
    packet_digest: str = Field(pattern=DIGEST)
    justification: str = Field(min_length=12, max_length=500)
    confirmed: bool
    acknowledged_no_authority: bool


class HumanReviewDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.upgrade-change-human-review-decision-request.v1", pattern=STABLE_ID
    )
    stage_id: str = Field(pattern=STABLE_ID)
    outcome: str = Field(pattern=r"^(approve|reject|needs_evidence|defer)$")
    rationale: str = Field(min_length=5, max_length=1000)
    acknowledged_no_authority: bool
    expected_version: int = Field(ge=1)


class HumanReviewStageData(BaseModel):
    stage_id: str
    sequence: int
    required_role_id: str
    quorum: int
    state: str
    packet_digest: str
    reviewer_id: str | None
    decision_id: str | None
    decided_at: datetime | None
    rationale: str | None


class HumanReviewDecisionData(BaseModel):
    decision_id: str
    stage_id: str
    request_version: int
    outcome: str
    reviewer_id: str
    reviewer_role_id: str
    rationale: str
    acknowledged_no_authority: bool
    decided_at: datetime


class HumanReviewData(BaseModel):
    review_id: str
    schema_version: str
    version: int
    state: str
    packet_id: str
    packet_digest: str
    requester_id: str
    risk_class: str
    change_class: str
    impacted_service_ids: list[str]
    evidence_digests: list[str]
    proposed_window_start: datetime
    proposed_window_end: datetime
    justification: str
    required_role_ids: list[str]
    stages: list[HumanReviewStageData]
    decisions: list[HumanReviewDecisionData]
    canonical_digest: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    reused: bool
    human_review_completed: bool
    approval_granted: bool
    itsm_dispatched: bool
    handoff_issued: bool
    workflow_executed: bool
    execution_authorized: bool
    infrastructure_mutation_performed: bool

    @classmethod
    def from_domain(cls, item: UpgradeChangeHumanReview) -> HumanReviewData:
        return cls.model_validate(
            {
                "review_id": item.review_id,
                "schema_version": item.schema_version,
                "version": item.version,
                "state": item.state.value,
                "packet_id": item.packet_id,
                "packet_digest": item.packet_digest,
                "requester_id": item.requester_id,
                "risk_class": item.risk_class,
                "change_class": item.change_class,
                "impacted_service_ids": list(item.impacted_service_ids),
                "evidence_digests": list(item.evidence_digests),
                "proposed_window_start": item.proposed_window_start,
                "proposed_window_end": item.proposed_window_end,
                "justification": item.justification,
                "required_role_ids": list(item.required_role_ids),
                "stages": [
                    {
                        "stage_id": stage.stage_id,
                        "sequence": stage.sequence,
                        "required_role_id": stage.required_role_id,
                        "quorum": stage.quorum,
                        "state": stage.state.value,
                        "packet_digest": stage.packet_digest,
                        "reviewer_id": stage.reviewer_id,
                        "decision_id": stage.decision_id,
                        "decided_at": stage.decided_at,
                        "rationale": stage.rationale,
                    }
                    for stage in item.stages
                ],
                "decisions": [
                    {
                        "decision_id": decision.decision_id,
                        "stage_id": decision.stage_id,
                        "request_version": decision.request_version,
                        "outcome": decision.outcome.value,
                        "reviewer_id": decision.reviewer_id,
                        "reviewer_role_id": decision.reviewer_role_id,
                        "rationale": decision.rationale,
                        "acknowledged_no_authority": decision.acknowledged_no_authority,
                        "decided_at": decision.decided_at,
                    }
                    for decision in item.decisions
                ],
                "canonical_digest": item.canonical_digest,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
                "expires_at": item.expires_at,
                "reused": item.reused,
                "human_review_completed": item.human_review_completed,
                "approval_granted": item.approval_granted,
                "itsm_dispatched": item.itsm_dispatched,
                "handoff_issued": item.handoff_issued,
                "workflow_executed": item.workflow_executed,
                "execution_authorized": item.execution_authorized,
                "infrastructure_mutation_performed": item.infrastructure_mutation_performed,
            }
        )


class HumanReviewResponse(BaseModel):
    data: HumanReviewData
    meta: ResponseMeta


class HumanReviewInboxData(BaseModel):
    items: list[HumanReviewData]
    next_cursor: str | None
    limit: int


class HumanReviewInboxResponse(BaseModel):
    data: HumanReviewInboxData
    meta: ResponseMeta


class CompletionReceiptCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.upgrade-human-review-completion-receipt-request.v1",
        pattern=STABLE_ID,
    )
    expected_review_version: int = Field(ge=1)
    acknowledged_evidence_only: bool


class CompletionStageEvidenceData(BaseModel):
    stage_id: str
    sequence: int
    required_role_id: str
    reviewer_id: str
    decision_id: str
    request_version: int
    outcome: str
    rationale_digest: str
    acknowledged_no_authority: bool
    decided_at: datetime


class CompletionReceiptData(BaseModel):
    receipt_id: str
    schema_version: str
    version: int
    review_id: str
    review_version: int
    review_digest: str
    review_expires_at: datetime
    packet_id: str
    packet_digest: str
    requester_id: str
    created_by: str
    risk_class: str
    change_class: str
    impacted_service_ids: list[str]
    evidence_digests: list[str]
    proposed_window_start: datetime
    proposed_window_end: datetime
    stages: list[CompletionStageEvidenceData]
    canonical_digest: str
    created_at: datetime
    reused: bool
    human_review_completed: bool
    completion_evidence_only: bool
    approval_granted: bool
    itsm_dispatched: bool
    notification_sent: bool
    handoff_issued: bool
    workflow_executed: bool
    execution_authorized: bool
    infrastructure_mutation_performed: bool

    @classmethod
    def from_domain(cls, item: HumanReviewCompletionReceipt) -> CompletionReceiptData:
        return cls.model_validate(
            {
                "receipt_id": item.receipt_id,
                "schema_version": item.schema_version,
                "version": item.version,
                "review_id": item.review_id,
                "review_version": item.review_version,
                "review_digest": item.review_digest,
                "review_expires_at": item.review_expires_at,
                "packet_id": item.packet_id,
                "packet_digest": item.packet_digest,
                "requester_id": item.requester_id,
                "created_by": item.created_by,
                "risk_class": item.risk_class,
                "change_class": item.change_class,
                "impacted_service_ids": list(item.impacted_service_ids),
                "evidence_digests": list(item.evidence_digests),
                "proposed_window_start": item.proposed_window_start,
                "proposed_window_end": item.proposed_window_end,
                "stages": [
                    {
                        "stage_id": stage.stage_id,
                        "sequence": stage.sequence,
                        "required_role_id": stage.required_role_id,
                        "reviewer_id": stage.reviewer_id,
                        "decision_id": stage.decision_id,
                        "request_version": stage.request_version,
                        "outcome": stage.outcome.value,
                        "rationale_digest": stage.rationale_digest,
                        "acknowledged_no_authority": stage.acknowledged_no_authority,
                        "decided_at": stage.decided_at,
                    }
                    for stage in item.stages
                ],
                "canonical_digest": item.canonical_digest,
                "created_at": item.created_at,
                "reused": item.reused,
                "human_review_completed": item.human_review_completed,
                "completion_evidence_only": item.completion_evidence_only,
                "approval_granted": item.approval_granted,
                "itsm_dispatched": item.itsm_dispatched,
                "notification_sent": item.notification_sent,
                "handoff_issued": item.handoff_issued,
                "workflow_executed": item.workflow_executed,
                "execution_authorized": item.execution_authorized,
                "infrastructure_mutation_performed": item.infrastructure_mutation_performed,
            }
        )


class CompletionReceiptResponse(BaseModel):
    data: CompletionReceiptData
    meta: ResponseMeta
